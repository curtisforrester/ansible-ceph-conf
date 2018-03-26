"""
"""
import os
import sys


# noinspection PyPep8Naming
class PwdMixin(object):
    # noinspection PyUnresolvedReferences
    def setUp(self):
        super(PwdMixin, self).setUp()

    # noinspection PyUnresolvedReferences
    def tearDown(self):
        super(PwdMixin, self).tearDown()

    @staticmethod
    def get_pwd():
        this_dir = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))
        return this_dir
