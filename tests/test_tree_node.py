__author__ = 'Bohdan Mushkevych'

import mock
import unittest

from settings import enable_test_mode
enable_test_mode()

from constants import TOKEN_SITE, TOKEN_CLIENT, PROCESS_SITE_YEARLY, PROCESS_SITE_MONTHLY, \
    PROCESS_SITE_DAILY, PROCESS_SITE_HOURLY, PROCESS_CLIENT_MONTHLY
from synergy.db.model.job import Job
from synergy.system import time_helper
from synergy.scheduler.tree import MultiLevelTree
from synergy.scheduler.tree_node import TreeNode, NodesCompositeState
from synergy.scheduler.process_hierarchy import ProcessHierarchy
from synergy.system.time_qualifier import *
from tests.state_machine_testing_utils import TEST_PRESET_TIMEPERIOD


def request_embryo_job_record(the_node, the_mock, is_finished):
    def the_function():
        the_node.job_record = the_mock
        the_node.job_record.is_finished = is_finished
    return the_function


class TestTreeNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestTreeNode, cls).setUpClass()

    def setUp(self):
        self.tree_mock = mock.create_autospec(MultiLevelTree)
        self.tree_mock.build_timeperiod = TEST_PRESET_TIMEPERIOD

        self.tree_mock.process_hierarchy = mock.create_autospec(ProcessHierarchy)
        self.tree_mock.process_hierarchy.get_child_by_qualifier = mock.MagicMock(return_value=PROCESS_SITE_HOURLY)

        self.parent_node_mock = mock.create_autospec(TreeNode)
        self.job_mock = mock.create_autospec(Job)
        self.the_node = TreeNode(self.tree_mock, self.parent_node_mock, PROCESS_SITE_HOURLY,
                                 TEST_PRESET_TIMEPERIOD, self.job_mock)
        self.parent_node_mock.children = {TEST_PRESET_TIMEPERIOD: self.the_node}

    def tearDown(self):
        del self.the_node
        del self.job_mock
        del self.tree_mock

    def test_find_counterpart_for(self):
        tree_four_level = MultiLevelTree(process_names=[PROCESS_SITE_YEARLY,
                                                        PROCESS_SITE_MONTHLY,
                                                        PROCESS_SITE_DAILY,
                                                        PROCESS_SITE_HOURLY],
                                         tree_name=TOKEN_SITE)

        tree_two_level = MultiLevelTree(process_names=[PROCESS_CLIENT_MONTHLY],
                                        tree_name=TOKEN_CLIENT)

        tree_four_level.build_tree()
        tree_two_level.build_tree()

        actual_yearly_timeperiod = time_helper.actual_timeperiod(QUALIFIER_YEARLY)
        actual_monthly_timeperiod = time_helper.actual_timeperiod(QUALIFIER_MONTHLY)
        actual_daily_timeperiod = time_helper.actual_timeperiod(QUALIFIER_DAILY)
        actual_hourly_timeperiod = time_helper.actual_timeperiod(QUALIFIER_HOURLY)

        # case 1 - left-to-right successful comparison
        node_a = tree_two_level.get_node(PROCESS_CLIENT_MONTHLY, actual_monthly_timeperiod)
        node_b = node_a.find_counterpart_in(tree_four_level)
        self.assertIsNotNone(node_b)
        self.assertEqual(node_a.timeperiod, node_b.timeperiod)

        # case 2 - right-to-left successful comparison
        node_a = tree_four_level.get_node(PROCESS_SITE_MONTHLY, actual_monthly_timeperiod)
        node_b = node_a.find_counterpart_in(tree_two_level)
        self.assertIsNotNone(node_b)
        self.assertEqual(node_a.timeperiod, node_b.timeperiod)

        # case 3 - right-to-left unsuccessful comparison
        node_a = tree_four_level.get_node(PROCESS_SITE_DAILY, actual_daily_timeperiod)
        node_b = node_a.find_counterpart_in(tree_two_level)
        self.assertIsNone(node_b)

        # case 4 - right-to-left unsuccessful comparison
        node_a = tree_four_level.get_node(PROCESS_SITE_HOURLY, actual_hourly_timeperiod)
        node_b = node_a.find_counterpart_in(tree_two_level)
        self.assertIsNone(node_b)

        # case 5 - right-to-left unsuccessful comparison
        node_a = tree_four_level.get_node(PROCESS_SITE_YEARLY, actual_yearly_timeperiod)
        node_b = node_a.find_counterpart_in(tree_two_level)
        self.assertIsNone(node_b)

    def test_validate_1(self):
        """
        test coverage:
        - request_embryo_job_record
        - request_reprocess
        - validate for all children
        """
        for _index in range(10):
            mock_job = mock.create_autospec(Job)
            mock_job.is_finished = True
            child_mock = mock.create_autospec(TreeNode)
            child_mock.job_record = mock.create_autospec(Job)
            child_mock.job_record.is_active = True
            self.the_node.children[_index] = child_mock

        # step 0: request Job record if current one is not set
        self.the_node.job_record = None
        self.the_node.request_reprocess = mock.Mock()
        self.the_node.request_skip = mock.Mock()
        self.the_node.request_embryo_job_record = mock.Mock(
            side_effect=request_embryo_job_record(self.the_node, self.job_mock, True))
        self.the_node.validate()

        # assertions:
        self.the_node.request_embryo_job_record.assert_called_once_with()
        self.the_node.request_reprocess.assert_called_once_with()
        self.assertEqual(len(self.the_node.request_skip.call_args_list), 0)

        for _, child in self.the_node.children.items():
            child.validate.assert_called_once_with()

    def test_validate_2(self):
        """
        test coverage:
        - request_skip
        """
        next_timeperiod = time_helper.increment_timeperiod(self.the_node.time_qualifier, TEST_PRESET_TIMEPERIOD)
        self.parent_node_mock.children[next_timeperiod] = mock.create_autospec(TreeNode)

        for _index in range(10):
            mock_job = mock.create_autospec(Job)
            mock_job.is_finished = True
            child_mock = mock.create_autospec(TreeNode)
            child_mock.job_record = mock.create_autospec(Job)
            child_mock.job_record.is_active = False
            child_mock.job_record.is_skipped = True
            self.the_node.children[_index] = child_mock

        # step 4: verify if this node should be transferred to STATE_SKIPPED
        self.the_node.job_record.is_skipped = False
        self.the_node.request_reprocess = mock.Mock()
        self.the_node.request_skip = mock.Mock()
        self.the_node.request_embryo_job_record = mock.Mock()
        self.the_node.validate()

        # assertions:
        self.assertEqual(len(self.the_node.request_embryo_job_record.call_args_list), 0)
        self.assertEqual(len(self.the_node.request_reprocess.call_args_list), 0)
        self.the_node.request_skip.assert_called_once_with()

    def test_is_finalizable(self):
        self.job_mock.is_active = True

        composite_state = NodesCompositeState()
        composite_state.all_finished = True
        self.the_node.dependent_on_composite_state = mock.Mock(return_value=composite_state)
        self.the_node.request_embryo_job_record = mock.Mock()
        for _index in range(10):
            mock_job = mock.create_autospec(Job)
            mock_job.is_finished = True
            child_mock = mock.create_autospec(TreeNode)
            child_mock.job_record = mock.create_autospec(Job)
            child_mock.job_record.is_active = True
            self.the_node.children[_index] = child_mock

        # happy-flow
        self.assertTrue(self.the_node.is_finalizable())

        # the job record of the node is still active
        self.the_node.job_record.is_active = False
        self.assertFalse(self.the_node.is_finalizable())

        # at least one of dependent nodes is not finished
        self.the_node.job_record.is_active = True
        composite_state.all_finished = False
        self.assertFalse(self.the_node.is_finalizable())

        # at least one child is still active
        composite_state.all_finished = True
        self.the_node.children[0].job_record.is_finished = False
        self.assertFalse(self.the_node.is_finalizable())


if __name__ == '__main__':
    unittest.main()
