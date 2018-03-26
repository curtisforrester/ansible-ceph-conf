import os
from unittest import TestCase
# noinspection SpellCheckingInspection
import cephconf.cephconf as cephconf
import mock
from mixins import PwdMixin


class AnsibleModuleFail(Exception):
    def __init__(self, rc, msg):
        self.rc = rc
        self.msg = msg


def module_fail(rc, msg):
    raise AnsibleModuleFail(rc=rc, msg=msg)


class CephConfTests(PwdMixin, TestCase):
    def setUp(self):
        self.ceph_conf_path = os.path.join(self.get_pwd(), 'ceph.conf')
        self.ceph_conf_template_path = os.path.join(self.get_pwd(), 'ceph_conf.yml')

    @classmethod
    def setUpClass(cls):
        if os.path.exists('/tmp/new_ceph.conf'):
            os.remove('/tmp/new_ceph.conf')

    def test_load_ceph(self):
        with mock.MagicMock() as ansible_mock:
            contents = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)
            self.assertTrue(contents)
            self.assertIsInstance(contents, dict)

    def test_load_ceph_missing(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            with self.assertRaises(AnsibleModuleFail) as ex:
                cephconf.load_existing_ceph(ansible_mock, '/invalid.conf')

            self.assertEqual(ex.exception.rc, 257)

    def test_load_srcfile_yml(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            contents = cephconf.load_srcfile(ansible_mock, self.ceph_conf_template_path)
            self.assertTrue(contents)
            self.assertIsInstance(contents, dict)

    def test_merge_items(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            conf = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)

            new_contents = {
                'global': {'debug_client': '1/1'}
            }

            self.assertEqual(conf['global']['debug_client'], '0/0')

            contents, _ = cephconf.merge_items(new_content=new_contents, curr_contents=conf)

            self.assertEqual(contents['global']['debug_client'], '1/1')

    def test_merge_yml_items(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            conf = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)
            template = cephconf.load_srcfile(ansible_mock, self.ceph_conf_template_path)

            self.assertEqual(conf['global']['debug_client'], '0/0')

            contents, _ = cephconf.merge_items(new_content=template, curr_contents=conf)

            self.assertIn('client.radosgw.deploy-3', contents)

    def test_update_items(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            conf = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)
            template = {
                'osd': {'only': 'item'}
            }

            self.assertIn('osd scrub sleep', conf.get('osd'))
            contents, _ = cephconf.update_items(new_content=template, curr_contents=conf)

            self.assertNotIn('osd scrub sleep', contents)
            self.assertEqual(contents.get('osd').keys(), ['only'])

    def test_remove_section(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            conf = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)

            template = {
                'osd.1': None,
                'osd': {'pool default crush rule': None}
            }

            self.assertIn('osd.1', conf)

            contents, changed = cephconf.remove_items(new_content=template, curr_contents=conf)

            self.assertTrue(changed)
            self.assertNotIn('osd.1', contents)
            self.assertNotIn('pool default crush rule', contents.get('osd'))

    def test_write_dest_file(self):
        with mock.MagicMock() as ansible_mock:
            ansible_mock.fail_json = module_fail

            conf = cephconf.load_existing_ceph(ansible_mock, self.ceph_conf_path)
            bk_file = cephconf.write_dest_file(ansible_mock, '/tmp/new_ceph.conf', backup=False, contents=conf)
            self.assertIsNone(bk_file)

            self.assertTrue(os.path.exists('/tmp/new_ceph.conf'))
