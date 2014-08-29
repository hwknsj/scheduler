__author__ = 'Bohdan Mushkevych'

from bson.objectid import ObjectId
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from threading import RLock
from system import time_helper
from system.decorator import thread_safe
from system.collection_context import COLLECTION_UNITS_OF_WORK
from system.process_context import ProcessContext
from db.error import DuplicateKeyError
from db.manager import ds_manager
from db.model import unit_of_work
from db.model.unit_of_work import UnitOfWork


class UnitOfWorkDao(object):
    """ Thread-safe Data Access Object for box_configuration table/collection """

    def __init__(self, logger):
        super(UnitOfWorkDao, self).__init__()
        self.logger = logger
        self.lock = RLock()
        self.ds = ds_manager.ds_factory(logger)

    @thread_safe
    def get_one(self, key):
        """ method finds unit_of_work record and returns it to the caller"""
        if not isinstance(key, ObjectId):
            # cast key to ObjectId
            key = ObjectId(key)

        query = {'_id': key}
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)

        document = collection.find_one(query)
        if document is None:
            msg = 'Unit_of_work with ID=%s was not found' % str(key)
            self.logger.warning(msg)
            raise LookupError(msg)
        return UnitOfWork(document)

    @thread_safe
    def get_reprocessing_candidates(self, since=None):
        """ method queries Unit Of Work whose <start_timeperiod> is younger than <since>
        and who could be candidates for re-processing """
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)

        query = {unit_of_work.STATE: {'$in': [unit_of_work.STATE_IN_PROGRESS,
                                              unit_of_work.STATE_INVALID,
                                              unit_of_work.STATE_REQUESTED]}}

        if since is None:
            cursor = collection.find(query).sort('_id', ASCENDING)
            candidates = [UnitOfWork(document) for document in cursor]
        else:
            candidates = []
            yearly_timeperiod = time_helper.cast_to_time_qualifier(QUALIFIER_YEARLY, since)
            query[unit_of_work.START_TIMEPERIOD] = {'$gte': yearly_timeperiod}

            cursor = collection.find(query).sort('_id', ASCENDING)
            for document in cursor:
                uow = UnitOfWork(document)
                if uow.process_name not in ProcessContext.PROCESS_CONTEXT:
                    # this is a decommissioned process
                    continue

                time_qualifier = ProcessContext.get_time_qualifier(uow.process_name)
                if time_qualifier == QUALIFIER_REAL_TIME:
                    time_qualifier = QUALIFIER_HOURLY
                process_specific_since = time_helper.cast_to_time_qualifier(time_qualifier, since)

                if process_specific_since <= uow.start_timeperiod:
                    candidates.append(uow)

        if len(candidates) == 0:
            raise LookupError('MongoDB has no reprocessing candidates units of work')
        return candidates

    @thread_safe
    def get_by_params(self, process_name, timeperiod, start_obj_id, end_obj_id):
        """ method finds unit_of_work record and returns it to the caller"""
        query = {unit_of_work.PROCESS_NAME: process_name,
                 unit_of_work.TIMEPERIOD: timeperiod,
                 unit_of_work.START_OBJ_ID: start_obj_id,
                 unit_of_work.END_OBJ_ID: end_obj_id}
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)

        document = collection.find_one(query)
        if document is None:
            raise LookupError('Unit_of_work satisfying query %r was not found' % query)
        return UnitOfWork(document)

    @thread_safe
    def update(self, uow):
        """ method finds unit_of_work record and change its status"""
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)
        return collection.save(uow.document, safe=True)

    @thread_safe
    def insert(self, uow):
        """ inserts unit of work to MongoDB. @throws DuplicateKeyError if such record already exist """
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)
        try:
            return collection.insert(uow.document, safe=True)
        except MongoDuplicateKeyError as e:
            exc = DuplicateKeyError(e)
            exc.start_id = uow.start_id
            exc.end_id = uow.end_id
            exc.process_name = uow.process_name
            exc.timeperiod = uow.start_timeperiod
            raise exc

    @thread_safe
    def remove(self, uow_id):
        collection = self.ds.connection(COLLECTION_UNITS_OF_WORK)
        return collection.remove(uow_id, safe=True)