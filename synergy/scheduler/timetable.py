__author__ = 'Bohdan Mushkevych'

import collections
from datetime import datetime
from threading import RLock

from synergy.db.dao.job_dao import JobDao
from synergy.db.model.job import Job
from synergy.conf import context
from synergy.conf import settings
from synergy.system import time_helper
from synergy.system.time_qualifier import *
from synergy.system.decorator import thread_safe
from synergy.scheduler.scheduler_constants import COLLECTION_JOB_HOURLY, COLLECTION_JOB_DAILY, \
    COLLECTION_JOB_MONTHLY, COLLECTION_JOB_YEARLY
from synergy.scheduler.tree import MultiLevelTree


class Timetable(object):
    """ Timetable holds all known process trees, where every node presents a timeperiod-driven job"""

    def __init__(self, logger):
        self.lock = RLock()
        self.logger = logger
        self.job_dao = JobDao(self.logger)

        # self.trees contain all of the trees and manages much of their life cycle
        # remember to enlist here all trees the system is working with
        self.trees = self._construct_trees_from_context()

        self._register_dependencies()
        self.load_tree()
        self.build_trees()
        self.validate()

        # state_machines is of type <dictionary> and is initialized from the synergy_scheduler.Scheduler.__init__
        self.state_machines = None

    def _construct_trees_from_context(self):
        trees = dict()
        for tree_name, context_entry in context.timetable_context.items():
            tree = MultiLevelTree(process_names=context_entry.enclosed_processes,
                                  timetable=self,
                                  tree_name=tree_name,
                                  mx_name=context_entry.mx_name,
                                  mx_page=context_entry.mx_page)
            trees[tree_name] = tree
        return trees

    def _register_dependencies(self):
        """ register dependencies between trees"""
        for tree_name, context_entry in context.timetable_context.items():
            tree = self.trees[tree_name]
            assert isinstance(tree, MultiLevelTree)
            for dependent_on in context_entry.dependent_on:
                dependent_on_tree = self.trees[dependent_on]
                assert isinstance(dependent_on_tree, MultiLevelTree)
                tree.register_dependent_on(dependent_on_tree)

    # *** node manipulation methods ***
    def _find_dependant_trees(self, tree_obj):
        """ returns list of trees that are dependent_on given tree_obj """
        dependant_trees = []
        for tree_name, tree in self.trees.items():
            if tree_obj in tree.dependent_on:
                dependant_trees.append(tree)
        return dependant_trees

    def _find_dependant_tree_nodes(self, node_a):
        dependant_nodes = set()
        for tree_b in self._find_dependant_trees(node_a.tree):
            node_b = node_a.find_counterpart_in(tree_b)
            if node_b is None:
                continue
            dependant_nodes.add(node_b)
        return dependant_nodes

    @thread_safe
    def reprocess_tree_node(self, tree_node, tx_context=None):
        """ method reprocesses the node and all its dependants and parent nodes """
        if not tx_context:
            # create transaction context if one was not provided
            tx_context = collections.defaultdict(dict)

        if tree_node.parent is None:
            # do not process 'root' - the only node that has None as 'parent'
            return tx_context
        if tree_node.timeperiod in tx_context[tree_node.process_name]:
            # the node has already been marked for re-processing
            return tx_context

        if tree_node.job_record.is_embryo:
            # the node does not require re-processing
            pass
        else:
            state_machine = self.state_machines[tree_node.job_record.process_name]
            state_machine.reprocess_job(tree_node.job_record)

        tx_context[tree_node.process_name][tree_node.timeperiod] = tree_node
        self.reprocess_tree_node(tree_node.parent, tx_context)

        dependant_nodes = self._find_dependant_tree_nodes(tree_node)
        for node in dependant_nodes:
            self.reprocess_tree_node(node, tx_context)

        return tx_context

    @thread_safe
    def skip_tree_node(self, tree_node):
        """ method skips given node job-record """
        state_machine = self.state_machines[tree_node.process_name]
        state_machine.skip_job(tree_node.job_record)

    @thread_safe
    def assign_job_record(self, tree_node):
        """ - looks for an existing job record in the DB, and if not found
            - creates a job record in STATE_EMBRYO and bind it to the given tree node """
        try:
            job_record = self.job_dao.get_one(tree_node.process_name, tree_node.timeperiod)
        except LookupError:
            state_machine = self.state_machines[tree_node.process_name]
            job_record = state_machine.create_job(tree_node.process_name, tree_node.timeperiod)
        tree_node.job_record = job_record

    # *** Tree-manipulation methods ***
    @thread_safe
    def get_tree(self, process_name):
        """ return tree that is managing time-periods for given process"""
        for tree_name, tree in self.trees.items():
            if process_name in tree:
                return tree

    @thread_safe
    def _build_tree_by_level(self, collection_name, since):
        """ method iterated thru all documents in all job collections and builds a tree of known system state"""
        try:
            unsupported_records = dict()
            job_records = self.job_dao.get_all(collection_name, since)
            for job_record in job_records:
                tree = self.get_tree(job_record.process_name)
                if tree is not None:
                    tree.update_node(job_record)
                else:
                    unsupported_records[job_record.process_name] = \
                        unsupported_records.get(job_record.process_name, 0) + 1

            for name, counter in unsupported_records.items():
                self.logger.warn('Skipping %r Job records for %s as no tree is handling it.' % (counter, name))

        except LookupError:
            self.logger.warn('No Job Records in %s.' % str(collection_name))

    @thread_safe
    def load_tree(self):
        """ method iterates thru all objects older than synergy_start_timeperiod parameter in job collections
        and loads them into this timetable"""
        timeperiod = settings.settings['synergy_start_timeperiod']
        yearly_timeperiod = time_helper.cast_to_time_qualifier(QUALIFIER_YEARLY, timeperiod)
        monthly_timeperiod = time_helper.cast_to_time_qualifier(QUALIFIER_MONTHLY, timeperiod)
        daily_timeperiod = time_helper.cast_to_time_qualifier(QUALIFIER_DAILY, timeperiod)
        hourly_timeperiod = time_helper.cast_to_time_qualifier(QUALIFIER_HOURLY, timeperiod)

        self._build_tree_by_level(COLLECTION_JOB_HOURLY, since=hourly_timeperiod)
        self._build_tree_by_level(COLLECTION_JOB_DAILY, since=daily_timeperiod)
        self._build_tree_by_level(COLLECTION_JOB_MONTHLY, since=monthly_timeperiod)
        self._build_tree_by_level(COLLECTION_JOB_YEARLY, since=yearly_timeperiod)

    @thread_safe
    def build_trees(self):
        """ method iterates thru all trees and ensures that all time-period nodes are created up till <utc_now>"""
        for tree_name, tree in self.trees.items():
            tree.build_tree()

    @thread_safe
    def validate(self):
        """validates that none of nodes in tree is improperly finalized and that every node has job_record"""
        for tree_name, tree in self.trees.items():
            tree.validate()

    @thread_safe
    def dependent_on_composite_state(self, job_record):
        """ :return instance of <NodesCompositeState> """
        assert isinstance(job_record, Job)
        tree = self.get_tree(job_record.process_name)
        node = tree.get_node(job_record.process_name, job_record.timeperiod)
        return node.dependent_on_composite_state()

    # *** Job manipulation methods ***
    @thread_safe
    def failed_on_processing_job_record(self, job_record):
        """ method is called from abstract_state_machine.manage_job to notify about job's failed processing
            if should_skip_node returns True - the node's job_record is transferred to STATE_SKIPPED """
        tree = self.get_tree(job_record.process_name)
        node = tree.get_node(job_record.process_name, job_record.timeperiod)
        if tree.should_skip_tree_node(node):
            self.skip_tree_node(node)

    @thread_safe
    def get_next_job_record(self, process_name):
        """ :returns: the next job record to work on for the given process"""
        tree = self.get_tree(process_name)
        node = tree.get_next_node(process_name)

        if node.job_record is None:
            self.assign_job_record(node)
        return node.job_record

    @thread_safe
    def is_job_record_finalizable(self, job_record):
        """ :return: True, if the node and all its children are either in STATE_PROCESSED or STATE_SKIPPED"""
        assert isinstance(job_record, Job)
        tree = self.get_tree(job_record.process_name)
        node = tree.get_node(job_record.process_name, job_record.timeperiod)
        return node.is_finalizable()

    @thread_safe
    def add_log_entry(self, process_name, timeperiod, msg):
        """ adds a non-persistent log entry to the tree node """
        tree = self.get_tree(process_name)
        node = tree.get_node(process_name, timeperiod)
        node.add_log_entry([datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), msg])
