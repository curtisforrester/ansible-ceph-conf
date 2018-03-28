#!/usr/bin/python
# -*- coding: utf-8 -*-

# Custom Ansible module to manage the ceph.conf file

from ConfigParser import RawConfigParser
import copy

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}

DOCUMENTATION = '''
---
module: cephconf
short_description: Manage ceph.conf File
extends_documentation_fragment: files
description:
    - Manage settings and sections within a ceph.conf file using Python RawConfigParser. This uses 
      a similar interface to the M(ini_file) Ansible module.
    - The parameters support individual keys and a source dict containing blocks to update.
version_added: "1.9.6"
options:
  src:
    description:
      - Path to the ceph.conf file. This file is updated if C(dest) is not supplied.
    required: true
    default: null
  path:
    description:
      - 'Path to the ceph.conf to write.  Aliases: I(dest), I(name)'
    required: true
    default: null
    aliases: ['dest', 'name'] 
  section:
    description:
      - Section name in ceph.conf file. This is added if C(state=present) automatically when
        a single value is being set. Not required if I(srcfile) is supplied.
    required: false
    default: null
  srcfile:
    description:
      - Path to a file containing source items to update to the ceph.conf. This can be a C(.yml),
        C(.json) or C(.ini)/C(.conf) file. The type is inferred from the filename extension.
  option:
    description:
      - if set (required for changing a I(value)), this is the name of the option.
      - May be omitted if adding/removing a whole I(section).
    required: false
    default: null
  value:
    description:
     - the string value to be associated with an I(option). May be omitted when removing an I(option).
    required: false
    default: null
  sorted:
    description:
     - To sort the sections and keys. Default is to output them in no specific order. I(Not yet supported)
    required: false
    default: no
    choices: [ "yes", "no" ]
  backup:
    description:
      - Create a backup file including the timestamp information so you can get
        the original file back if you somehow clobbered it incorrectly.
    required: false
    default: "no"
    choices: [ "yes", "no" ]
  others:
     description:
       - all arguments accepted by the M(file) module also work here
     required: false
  state:
     description:
       - If set to C(absent) the option or section will be removed if present instead of created. If used
         with C(srcfile) this will remove only the section options listed (value will be ignored in the 
         srcfile).
       - If set to C(merge) and C(srcfile) is supplied this will create new sections/options or
         merge the items to existing sections. Any existing options will have their value updated
         from the C(srcfile) items.
       - If set to C(present) sections will be replaced with the options in C(srcfile). To add/update
         section items use C(merge).
     required: false
     default: "present"
     choices: [ "present", "absent", "merge" ]
author:
    - "Curtis Forrester (@curtisforrester)"
'''

EXAMPLES = '''
# Update "osd recovery threads = 5 is in section "[global]".
- cephconf:
    src: /etc/ceph/ceph.conf
    section: global
    option: osd recovery threads
    value: 5

# To remove an obsoleted or unneeded key
- cephconf:
    src: /etc/ceph/ceph.conf
    section: global
    option: obsolete_key
    state: absent
    
# To merge the contents from a temp source file and put ceph.conf in temp file
- cephconf:
    src: /etc/ceph/ceph.conf
    dest: /tmp/ceph_merged.conf
    srcfile: /tmp/ceph_conf_updates.yml
    state: merge
    
# To add or replace sections from a source file
- cephconf:
    src: /etc/ceph/ceph.conf
    srcfile: /tmp/ceph_conf_updates.yml
    state: present
    
# To remove a set of options from the dest from a source file that might look like this:

#global:
#  obsolete_option: 0
#  another_obsolete_option: 0

- cephconf:
    dest: /etc/ceph/ceph.conf
    srcfile: /tmp/ceph_conf_remove.yml
    state: absent
'''


def load_existing_ceph(this_module, filename=None):
    """

    :param this_module: This Ansible module
    :type this_module: AnsibleModule

    :param filename: The path to an existing ceph.conf file
    :type filename: str

    :return: A dict with the contents of the ceph.conf INI file
    :rtype: dict
    """
    if not os.path.exists(filename):
        this_module.fail_json(rc=257, msg='Ceph.conf file %s does not exist !' % filename)

    config = RawConfigParser()
    config.read(filename)

    return config_parser_to_dict(config=config)


def config_parser_to_dict(config):
    """
    Translates the items in the config parser object to dict.

    :param config: RawConfigParser

    :return: Dictionary with the contents
    :rtype: dict
    """
    contents = {}
    for section in config.sections():
        contents.update({section: {item[0]: item[1] for item in config.items(section)}})

    return contents


def load_srcfile(this_module, filename):
    """
    Load the contents of a specified source file to merge/update from.

    :param this_module: This Ansible module instance

    :param filename: Path to the srcfile
    :type filename: str

    :return: The contents as dictionary. If filename does not exist, return empty dict.
    :rtype: dict
    """
    if not os.path.exists(filename):
        return {}

    if filename.endswith('.yml'):
        import yaml
        with open(filename) as fp:
            contents = yaml.load(fp)
            return contents

    elif filename.endswith('.json'):
        import json
        with open(filename) as fp:
            contents = json.load(fp)
            return contents

    elif filename.endswith('.ini') or filename.endswith('.conf'):
        config = RawConfigParser()
        config.read(filename)

        return config_parser_to_dict(config=config)

    else:
        this_module.fail_json(rc=1, msg='Unknown srcfile file type. Please use .yml, .json, .ini or .conf')


def merge_items(new_content, curr_contents):
    """
    Given a dict of either partial or full items, update the curr_contents to
    create the target contents.

    This will create missing items; for existing items they will be set to the values in
    the new_content dict.

    :param new_content: Dict to update to curr_contents
    :type: dict

    :param curr_contents: Current dict content for conf file
    :type: dict

    :return: The result dict and changed flag (always True here)
    :rtype: tuple[dict, bool]
    """
    shadow = copy.deepcopy(curr_contents)

    for section in new_content:
        if section in shadow:
            shadow[section].update(new_content.get(section) or {})
        else:
            shadow[section] = new_content.get(section)

    return shadow, True


def update_items(new_content, curr_contents):
    """
    Update the target in curr_contents from the new_content. This will replace.

    :param new_content: Dict to update to curr_contents
    :type: dict

    :param curr_contents: Current dict content for conf file
    :type: dict

    :return: The result dict and changed flag (always True here)
    :rtype: tuple[dict, bool]
    """
    target = copy.copy(curr_contents)
    target.update(new_content)

    return target, True


def remove_items(new_content, curr_contents):
    """

    :param new_content: Dict to update to curr_contents
    :type: dict

    :param curr_contents: Current dict content for conf file
    :type: dict

    :return: The result dict and changed flag
    :rtype: tuple[dict, bool]
    """
    shadow = copy.deepcopy(curr_contents)
    changed = False

    for section in new_content:
        if section not in shadow:
            continue

        if new_content.get(section) is None:
            del shadow[section]
            changed = True
            continue

        for key in new_content[section]:
            if key in shadow.get(section):
                changed = True
                del shadow.get(section)[key]

    return shadow, changed


# noinspection SpellCheckingInspection
def write_dest_file(this_module, filename, backup, contents):
    """
    Write the contents to the destination file. Note that this fully regenerates
    the file from the contents dict - this will have been updated to reflect
    the requested actions.

    :param this_module:

    :param filename: The destination ceph.conf filename
    :type filename: str

    :param backup: If True backup the current ceph.conf
    :type backup: bool

    :param contents: The updated ceph.conf contents dict
    :type contents: dict
    :return:
    """
    backup_file = None

    if os.path.exists(filename) and backup:
        backup_file = this_module.backup_local(filename)

    target = RawConfigParser()
    # print(contents)

    # Construct the INI settings
    for section in contents:
        if not target.has_section(section):
            target.add_section(section)

        for option in contents.get(section):

            value = contents.get(section).get(option)
            target.set(section, option, value)

    with open(filename, 'w') as fp:
        target.write(fp)

    return backup_file


def main():
    # noinspection PyShadowingBuiltins
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(required=True),
            path=dict(aliases=['dest', 'name'], required=True),
            section=dict(required=False),
            srcfile=dict(required=False),
            option=dict(required=False),
            value=dict(required=False),
            backup=dict(default='no', type='bool'),
            state=dict(default='present', choices=['present', 'absent', 'merge']),
        ),
        add_file_common_args=True,
        supports_check_mode=True
    )

    src = os.path.expanduser(module.params['src'])
    dest = module.params['dest']
    if not dest:
        dest = src
    else:
        dest = os.path.expanduser(dest)
    section = module.params['section']
    srcfile = module.params['srcfile']
    option = module.params['option']
    value = module.params['value']
    state = module.params['state']
    backup = module.params['backup']

    run_module(this_module=module,
               src=src,
               dest=dest,
               section=section,
               srcfile=srcfile,
               option=option,
               value=value,
               state=state,
               backup=backup)


def run_module(this_module, src, dest, section, srcfile, option, value, state, backup):
    ceph_contents = load_existing_ceph(this_module=this_module, filename=src)
    changed_ceph_contents = {}

    # Load from srcfile or grab the option/value from parameters
    if srcfile:
        new_content = load_srcfile(this_module=this_module, filename=srcfile)

    elif not section:
        new_content = {}
        this_module.fail_json(rc=1, msg='Required parameter "section" not found.')

    else:
        new_content = {section: {option: value}}
        if state == 'present':
            state = 'merge'

    # Now update the final content dict
    changed = False
    # print('State: {}'.format(state))
    # print(new_content)

    if state == 'merge':
        changed_ceph_contents, changed = merge_items(new_content=new_content,
                                                     curr_contents=ceph_contents)

    elif state == 'present':
        changed_ceph_contents, changed = update_items(new_content=new_content,
                                                      curr_contents=ceph_contents)

    elif state == 'absent':
        changed_ceph_contents, changed = remove_items(new_content=new_content,
                                                      curr_contents=ceph_contents)

    backup_file = None
    # print(changed_ceph_contents)

    if changed and changed_ceph_contents and not this_module.check_mode:
        backup_file = write_dest_file(this_module=this_module, filename=dest, backup=backup, contents=changed_ceph_contents)

    if not this_module.check_mode:
        file_args = this_module.load_file_common_arguments(this_module.params)
        changed = this_module.set_fs_attributes_if_different(file_args, changed)

    results = {'changed': changed, 'msg': 'Done', 'dest': dest, 'diff': ''}
    if backup_file is not None:
        results['backup_file'] = backup_file

    # Mission complete
    # print('\n{}'.format(results))
    this_module.exit_json(**results)


# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
