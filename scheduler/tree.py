__author__ = 'Bohdan Mushkevych'

from db.model import time_table_record
from datetime import datetime, timedelta
from tree_node import TreeNode, LinearNode
from settings import settings
from system import time_helper
from system.time_helper import cast_to_time_qualifier
from system.process_context import ProcessContext

MAX_NUMBER_OF_RETRIES = 3    # number of times a node is re-run before it is considered STATE_SKIPPED
LIFE_SUPPORT_HOURS = 48      # number of hours that node is retried infinite number of times


class AbstractTree(object):
    """Linear timeline structure, presenting array of timetable_records"""

    def __init__(self, node_klass, category=None, mx_page=None):
        """
        @parameter node_klass: presents descendant of the AbstractNode class, that is used to instantiate nodes of the tree
        @optional @parameter category: is used by MX only as visual vertical name
        @optional @parameter mx_page: is used by MX only as anchor to specific page
        """
        self.build_timeperiod = None
        self.validation_timestamp = None
        self.reprocess_callbacks = []
        self.skip_callbacks = []
        self.create_timetable_record_callbacks = []
        self.category = category
        self.mx_page = mx_page
        self.node_klass = node_klass
        self.root = node_klass(self, None, None, None, None)
        self.dependent_on = []

    # *** PUBLIC METHODS ***
    def register_dependent_on(self, tree):
        """registering tree that we are dependent on.
        example: horizontal client should not be finalized until we have finalized vertical site for the same period"""
        self.dependent_on.append(tree)

    def unregister_dependent_on(self, tree):
        """unregistering tree that we are dependent on"""
        if tree in self.dependent_on:
            self.dependent_on.remove(tree)

    def register_reprocess_callback(self, function):
        """method that allows outside functionality to listen for _reprocess_requests_"""
        self.reprocess_callbacks.append(function)

    def unregister_reprocess_callback(self, function):
        """method that allows outside functionality to abandon _reprocess_requests_ listening"""
        if function in self.reprocess_callbacks:
            self.reprocess_callbacks.remove(function)

    def register_skip_callback(self, function):
        """method that allows outside functionality to listen for _skip_requests_"""
        self.skip_callbacks.append(function)

    def unregister_skip_callback(self, function):
        """method that allows outside functionality to abandon _skip_requests_ listening"""
        if function in self.skip_callbacks:
            self.skip_callbacks.remove(function)

    def register_timetable_callbacks(self, function):
        """method that allows outside functionality to listen for _create_embryo_timetable_record_requests_"""
        self.create_timetable_record_callbacks.append(function)

    def unregister_timetable_callback(self, function):
        """method that allows outside functionality to abandon _create_embryo_timetable_record_requests_ listening"""
        if function in self.create_timetable_record_callbacks:
            self.create_timetable_record_callbacks.remove(function)

    # *** PROTECTED METHODS ***
    def _build_tree(self, rebuild, process_name, method_get_node):
        """method builds tree by iterating from the synergy_start_timeperiod to current time
        and inserting corresponding nodes"""
        time_qualifier = ProcessContext.get_time_qualifier(process_name)
        if rebuild or self.build_timeperiod is None:
            timeperiod = settings['synergy_start_timeperiod']
            timeperiod = cast_to_time_qualifier(time_qualifier, timeperiod)
        else:
            timeperiod = self.build_timeperiod

        actual_timeperiod = time_helper.actual_timeperiod(time_qualifier)
        while actual_timeperiod >= timeperiod:
            method_get_node(timeperiod)
            timeperiod = time_helper.increment_timeperiod(time_qualifier, timeperiod)

        self.build_timeperiod = actual_timeperiod

    def _get_next_parent_node(self, parent):
        """ Used by _get_next_node, this method is called to find next possible parent.
        For example if timeperiod 2011010200 has all children processed, but is not processed yet
        then it makes sense to look in 2011010300 for hourly nodes"""
        parent_of_parent = parent.parent
        if parent_of_parent is None:
            # here, we work at yearly/linear level
            return None

        sorted_keys = sorted(parent_of_parent.children.keys())
        index = sorted_keys.index(parent.timeperiod)
        if index + 1 >= len(sorted_keys):
            return None
        else:
            return parent_of_parent.children[sorted_keys[index + 1]]

    def _get_next_node(self, parent):
        """ Looks for next node to process """
        sorted_keys = sorted(parent.children.keys())
        for key in sorted_keys:
            node = parent.children[key]
            if node.timetable_record is None:
                node.request_timetable_record()
                return node
            elif self._skip_the_node(node):
                continue
            elif node.timetable_record.state in [time_table_record.STATE_FINAL_RUN,
                                                 time_table_record.STATE_IN_PROGRESS,
                                                 time_table_record.STATE_EMBRYO]:
                return node

        # special case, when all children of the parent node are not suitable for processing
        new_parent = self._get_next_parent_node(parent)
        if new_parent is not None:
            # in case all nodes are processed or blocked - look for next valid parent node
            return self._get_next_node(new_parent)
        else:
            # if all valid parents are exploited - return current node
            process_name = parent.children[sorted_keys[0]].process_name
            time_qualifier = parent.children[sorted_keys[0]].time_qualifier
            actual_timeperiod = time_helper.actual_timeperiod(time_qualifier)
            return self.get_node_by_process(process_name, actual_timeperiod)

    # *** INHERITANCE INTERFACE ***
    def build_tree(self, rebuild=False):
        """method builds tree by iterating from the synergy_start_timeperiod to current time
        and inserting corresponding nodes"""
        pass

    def _skip_the_node(self, node):
        """Method is used during _get_next_node calculations.
        Returns True in case node shall be _skipped_"""
        pass

    def is_managing_process(self, process_name):
        """method returns True if process_name is registered on Timeline during creation"""
        pass

    def get_next_node_by_process(self, process_name):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        pass

    def update_node_by_process(self, process_name, timetable_record):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        pass

    def get_node_by_process(self, process_name, timeperiod):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        pass

    def validate(self):
        """method starts validation of the tree.
        @see AbstractNode.validate"""
        for timeperiod in self.root.children:
            child = self.root.children[timeperiod]
            child.validate()
        self.validation_timestamp = datetime.utcnow()


class TwoLevelTree(AbstractTree):
    """Linear timeline structure, presenting array of timetable_records"""

    def __init__(self, process_name, category=None, mx_page=None):
        super(TwoLevelTree, self).__init__(LinearNode, category, mx_page)
        self.process_name = process_name

    # *** SPECIFIC METHODS ***
    def __get_node(self, timeperiod):
        node = self.root.children.get(timeperiod)
        if node is None:
            node = LinearNode(self, self.root, self.process_name, timeperiod, None)
            node.request_timetable_record()
            self.root.children[timeperiod] = node

        return node

    def __update_node(self, timetable_record):
        node = self.__get_node(timetable_record.timeperiod)
        node.timetable_record = timetable_record

    # *** INHERITANCE INTERFACE ***
    def build_tree(self, rebuild=False):
        """method builds timeline by iterating from the synergy_start_timeperiod to current time
        and inserting nodes"""
        self._build_tree(rebuild, self.process_name, self.__get_node)

    def _skip_the_node(self, node):
        """Method is used during _get_next_node calculations.
        Returns True in case node shall be _skipped_"""
        if node.timetable_record.state in [time_table_record.STATE_SKIPPED, time_table_record.STATE_PROCESSED]:
            return True
        return node.timetable_record.number_of_failures > MAX_NUMBER_OF_RETRIES

    def is_managing_process(self, process_name):
        """method returns True if process_name is registered on Timeline during creation"""
        if process_name == self.process_name:
            return True
        return False

    def get_next_node_by_process(self, process_name):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        if process_name == self.process_name:
            return self._get_next_node(self.root)
        else:
            raise ValueError('unknown requested process: %s vs %s' % (process_name, self.process_name))

    def update_node_by_process(self, process_name, timetable_record):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        if process_name == self.process_name:
            return self.__update_node(timetable_record)
        else:
            raise ValueError('unknown requested process: %s vs %s' % (process_name, self.process_name))

    def get_node_by_process(self, process_name, timeperiod):
        """ method is used to keep consistency with Three/FourLevelTree interface"""
        if process_name == self.process_name:
            return self.__get_node(timeperiod)
        else:
            raise ValueError('unknown requested process: %s vs %s' % (process_name, self.process_name))


class ThreeLevelTree(AbstractTree):
    """Three level tree present structure, monitoring: yearly, monthly and daily time-periods"""

    def __init__(self, process_yearly, process_monthly, process_daily, category=None, mx_page=None):
        super(ThreeLevelTree, self).__init__(TreeNode, category, mx_page)
        self.process_yearly = process_yearly
        self.process_monthly = process_monthly
        self.process_daily = process_daily

    # *** PRIVATE METHODS TO BUILD AND OPERATE TREE ***
    def __get_yearly_node(self, timeperiod):
        node = self.root.children.get(timeperiod)
        if node is None:
            node = TreeNode(self, self.root, self.process_yearly, timeperiod, None)
            self.root.children[timeperiod] = node

        return node

    def __get_monthly_node(self, timeperiod):
        time_qualifier = ProcessContext.get_time_qualifier(self.process_yearly)
        timeperiod_yearly = cast_to_time_qualifier(time_qualifier, timeperiod)
        parent = self.__get_yearly_node(timeperiod_yearly)

        node = parent.children.get(timeperiod)
        if node is None:
            node = TreeNode(self, parent, self.process_monthly, timeperiod, None)
            parent.children[timeperiod] = node

        return node

    def __get_daily_node(self, timeperiod):
        time_qualifier = ProcessContext.get_time_qualifier(self.process_monthly)
        timeperiod_monthly = cast_to_time_qualifier(time_qualifier, timeperiod)
        parent = self.__get_monthly_node(timeperiod_monthly)

        node = parent.children.get(timeperiod)
        if node is None:
            node = TreeNode(self, parent, self.process_daily, timeperiod, None)
            parent.children[timeperiod] = node

        return node

    def __get_next_yearly_node(self):
        parent = self.root
        return self._get_next_node(parent)

    def __get_next_monthly_node(self):
        parent = self.__get_next_yearly_node()
        return self._get_next_node(parent)

    def __get_next_daily_node(self):
        parent = self.__get_next_monthly_node()
        return self._get_next_node(parent)

    # *** INHERITANCE INTERFACE ***
    def build_tree(self, rebuild=False):
        """method builds tree by iterating from the synergy_start_timeperiod to current time
        and inserting corresponding nodes"""
        self._build_tree(rebuild, self.process_daily, self.__get_daily_node)

    def get_node_by_process(self, process_name, timeperiod):
        if process_name == self.process_yearly:
            return self.__get_yearly_node(timeperiod)
        if process_name == self.process_monthly:
            return self.__get_monthly_node(timeperiod)
        if process_name == self.process_daily:
            return self.__get_daily_node(timeperiod)

    def update_node_by_process(self, process_name, timetable_record):
        if process_name == self.process_yearly:
            node = self.__get_yearly_node(timetable_record.timeperiod)
        elif process_name == self.process_monthly:
            node = self.__get_monthly_node(timetable_record.timeperiod)
        elif process_name == self.process_daily:
            node = self.__get_daily_node(timetable_record.timeperiod)
        else:
            raise ValueError('unknown process name: %s' % process_name)
        node.timetable_record = timetable_record

    def _skip_the_node(self, node):
        """Method is used during _get_next_node calculations.
        Returns True in case node shall be _skipped_"""
        # case 1: node processing is complete
        if node.timetable_record.state in [time_table_record.STATE_SKIPPED,
                                           time_table_record.STATE_PROCESSED]:
            return True

        # case 2: this is a daily leaf node. retry this time_period for INFINITE_RETRY_HOURS
        if node.process_name == self.process_daily:
            if len(node.children) == 0:
                # no children - this is a leaf
                creation_time = time_helper.synergy_to_datetime(node.time_qualifier, node.timeperiod)
                if datetime.utcnow() - creation_time < timedelta(hours=LIFE_SUPPORT_HOURS):
                    return False
                else:
                    return node.timetable_record.number_of_failures > MAX_NUMBER_OF_RETRIES

        # case 3: here we process process_daily, process_monthly and process_yearly that have children
        # iterate thru children and check if all of them are in STATE_SKIPPED (i.e. no data for parent to process)
        # if any is still in processing (i.e. has produced some data) - then we can not skip parent of the child node
        # case 3': consider parent as worth processing (i.e. do not skip) if child's timetable_record is None
        all_children_spoiled = True
        for key in node.children.keys():
            child = node.children[key]
            if child.timetable_record is None or \
                    (child.timetable_record.number_of_failures <= MAX_NUMBER_OF_RETRIES
                     and child.timetable_record.state != time_table_record.STATE_SKIPPED):
                all_children_spoiled = False
                break
        return all_children_spoiled

    def get_next_node_by_process(self, process_name):
        if process_name == self.process_yearly:
            return self.__get_next_yearly_node()
        if process_name == self.process_monthly:
            return self.__get_next_monthly_node()
        if process_name == self.process_daily:
            return self.__get_next_daily_node()

    def is_managing_process(self, process_name):
        """method returns True if process_name is among processes (yearly/monthly/daily etc),
        registered on Tree creation"""
        if process_name == self.process_yearly \
            or process_name == self.process_monthly \
            or process_name == self.process_daily:
            return True
        return False


class FourLevelTree(ThreeLevelTree):
    """Four level tree present structure, monitoring: yearly, monthly, daily and hourly time-periods"""

    def __init__(self, process_yearly, process_monthly, process_daily, process_hourly, category=None, mx_page=None):
        super(FourLevelTree, self).__init__(process_yearly, process_monthly, process_daily, category, mx_page)
        self.process_hourly = process_hourly

    # *** PRIVATE METHODS ***
    def __get_hourly_node(self, timeperiod):
        time_qualifier = ProcessContext.get_time_qualifier(self.process_daily)
        timeperiod_daily = cast_to_time_qualifier(time_qualifier, timeperiod)
        parent = self._ThreeLevelTree__get_daily_node(timeperiod_daily)

        node = parent.children.get(timeperiod)
        if node is None:
            node = TreeNode(self, parent, self.process_hourly, timeperiod, None)
            parent.children[timeperiod] = node

        return node

    def __get_next_hourly_node(self):
        parent = self._ThreeLevelTree__get_next_daily_node()
        return self._get_next_node(parent)

    # *** INHERITANCE INTERFACE ***
    def build_tree(self, rebuild=False):
        """@see ThreeLevelTree.build_tree """
        self._build_tree(rebuild, self.process_hourly, self.__get_hourly_node)

    def is_managing_process(self, process_name):
        """@see ThreeLevelTree.is_managing_process"""
        if process_name == self.process_hourly:
            return True
        else:
            return super(FourLevelTree, self).is_managing_process(process_name)

    def get_next_node_by_process(self, process_name):
        if process_name == self.process_hourly:
            return self.__get_next_hourly_node()
        else:
            return super(FourLevelTree, self).get_next_node_by_process(process_name)

    def get_node_by_process(self, process_name, timeperiod):
        if process_name == self.process_hourly:
            return self.__get_hourly_node(timeperiod)
        else:
            return super(FourLevelTree, self).get_node_by_process(process_name, timeperiod)

    def update_node_by_process(self, process_name, timetable_record):
        if process_name == self.process_hourly:
            node = self.__get_hourly_node(timetable_record.timeperiod)
            node.timetable_record = timetable_record
        else:
            return super(FourLevelTree, self).update_node_by_process(process_name, timetable_record)

    def _skip_the_node(self, node):
        """Method is used during _get_next_node calculations.
        Returns True in case node shall be _skipped_"""
        if node.process_name == self.process_hourly:
            if node.timetable_record.state in [time_table_record.STATE_SKIPPED, time_table_record.STATE_PROCESSED]:
                return True
            return node.timetable_record.number_of_failures > MAX_NUMBER_OF_RETRIES
        else:
            return super(FourLevelTree, self)._skip_the_node(node)
