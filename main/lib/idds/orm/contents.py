#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019 - 2022


"""
operations related to Requests.
"""

import datetime

import sqlalchemy
from sqlalchemy import func
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.sql.expression import asc

from idds.common import exceptions
from idds.common.constants import (ContentType, ContentStatus, ContentLocking,
                                   ContentRelationType)
from idds.orm.base.session import read_session, transactional_session
from idds.orm.base import models


def create_content(request_id, workload_id, transform_id, coll_id, map_id, scope, name,
                   min_id, max_id, content_type=ContentType.File,
                   status=ContentStatus.New, content_relation_type=ContentRelationType.Input,
                   bytes=0, md5=None, adler32=None, processing_id=None, storage_id=None, retries=0,
                   locking=ContentLocking.Idle, path=None, expired_at=None, content_metadata=None):
    """
    Create a content.

    :param request_id: The request id.
    :param workload_id: The workload id.
    :param transform_id: transform id.
    :param coll_id: collection id.
    :param map_id: The id to map inputs to outputs.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.
    :param status: content status.
    :param bytes: The size of the content.
    :param md5: md5 checksum.
    :param alder32: adler32 checksum.
    :param processing_id: The processing id.
    :param storage_id: The storage id.
    :param retries: The number of retries.
    :param path: The content path.
    :param expired_at: The datetime when it expires.
    :param content_metadata: The metadata as json.

    :returns: content.
    """

    new_content = models.Content(request_id=request_id, workload_id=workload_id,
                                 transform_id=transform_id, coll_id=coll_id, map_id=map_id,
                                 scope=scope, name=name, min_id=min_id, max_id=max_id,
                                 content_type=content_type, content_relation_type=content_relation_type,
                                 status=status, bytes=bytes, md5=md5,
                                 adler32=adler32, processing_id=processing_id, storage_id=storage_id,
                                 retries=retries, path=path, expired_at=expired_at, locking=locking,
                                 content_metadata=content_metadata)
    return new_content


@transactional_session
def add_content(request_id, workload_id, transform_id, coll_id, map_id, scope, name, min_id=0, max_id=0,
                content_type=ContentType.File, status=ContentStatus.New, content_relation_type=ContentRelationType.Input,
                bytes=0, md5=None, adler32=None, processing_id=None, storage_id=None, retries=0,
                locking=ContentLocking.Idle, path=None, expired_at=None, content_metadata=None, session=None):
    """
    Add a content.

    :param request_id: The request id.
    :param workload_id: The workload id.
    :param transform_id: transform id.
    :param coll_id: collection id.
    :param map_id: The id to map inputs to outputs.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.
    :param status: content status.
    :param bytes: The size of the content.
    :param md5: md5 checksum.
    :param alder32: adler32 checksum.
    :param processing_id: The processing id.
    :param storage_id: The storage id.
    :param retries: The number of retries.
    :param path: The content path.
    :param expired_at: The datetime when it expires.
    :param content_metadata: The metadata as json.

    :raises DuplicatedObject: If a collection with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: content id.
    """

    try:
        new_content = create_content(request_id=request_id, workload_id=workload_id, transform_id=transform_id,
                                     coll_id=coll_id, map_id=map_id, content_relation_type=content_relation_type,
                                     scope=scope, name=name, min_id=min_id, max_id=max_id,
                                     content_type=content_type, status=status, bytes=bytes, md5=md5,
                                     adler32=adler32, processing_id=processing_id, storage_id=storage_id,
                                     retries=retries, path=path, expired_at=expired_at,
                                     content_metadata=content_metadata)
        new_content.save(session=session)
        content_id = new_content.content_id
        return content_id
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Content transform_id:map_id(%s:%s) already exists!: %s' %
                                          (transform_id, map_id, error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def add_contents(contents, bulk_size=10000, session=None):
    """
    Add contents.

    :param contents: dict of contents.
    :param session: session.

    :raises DuplicatedObject: If a collection with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: content id.
    """
    default_params = {'request_id': None, 'workload_id': None,
                      'transform_id': None, 'coll_id': None, 'map_id': None,
                      'scope': None, 'name': None, 'min_id': 0, 'max_id': 0,
                      'content_type': ContentType.File, 'status': ContentStatus.New,
                      'locking': ContentLocking.Idle, 'content_relation_type': ContentRelationType.Input,
                      'bytes': 0, 'md5': None, 'adler32': None, 'processing_id': None,
                      'storage_id': None, 'retries': 0, 'path': None,
                      'expired_at': datetime.datetime.utcnow() + datetime.timedelta(days=30),
                      'content_metadata': None}

    for content in contents:
        for key in default_params:
            if key not in content:
                content[key] = default_params[key]

    sub_params = [contents[i:i + bulk_size] for i in range(0, len(contents), bulk_size)]

    try:
        for sub_param in sub_params:
            session.bulk_insert_mappings(models.Content, sub_param)
        content_ids = [None for _ in range(len(contents))]
        return content_ids
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Duplicated objects: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@read_session
def get_content(content_id=None, coll_id=None, scope=None, name=None, content_type=None, min_id=0, max_id=0, to_json=False, session=None):
    """
    Get contentor raise a NoObject exception.

    :param content_id: content id.
    :param coll_id: collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: Content.
    """

    try:
        if content_id:
            query = session.query(models.Content)\
                           .filter(models.Content.content_id == content_id)
        else:
            if content_type in [ContentType.File, ContentType.File.value]:
                query = session.query(models.Content)\
                               .with_hint(models.Content, "INDEX(CONTENTS CONTENTS_ID_NAME_IDX)", 'oracle')\
                               .filter(models.Content.coll_id == coll_id)\
                               .filter(models.Content.scope == scope)\
                               .filter(models.Content.name == name)\
                               .filter(models.Content.content_type == content_type)
            else:
                query = session.query(models.Content)\
                               .with_hint(models.Content, "INDEX(CONTENTS CONTENTS_ID_NAME_IDX)", 'oracle')\
                               .filter(models.Content.coll_id == coll_id)\
                               .filter(models.Content.scope == scope)\
                               .filter(models.Content.name == name)\
                               .filter(models.Content.min_id == min_id)\
                               .filter(models.Content.max_id == max_id)
                if content_type:
                    query = query.filter(models.Content.content_type == content_type)

        ret = query.first()
        if not ret:
            return None
        else:
            if to_json:
                return ret.to_dict_json()
            else:
                return ret.to_dict()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('content(content_id: %s, coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s) cannot be found: %s' %
                                  (content_id, coll_id, scope, name, content_type, min_id, max_id, error))
    except Exception as error:
        raise error


@read_session
def get_match_contents(coll_id, scope, name, content_type=None, min_id=None, max_id=None, to_json=False, session=None):
    """
    Get contents which matches the query or raise a NoObject exception.

    :param coll_id: collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of Content ids.
    """

    try:
        query = session.query(models.Content)\
                       .with_hint(models.Content, "INDEX(CONTENTS CONTENTS_ID_NAME_IDX)", 'oracle')\
                       .filter(models.Content.coll_id == coll_id)\
                       .filter(models.Content.scope == scope)\
                       .filter(models.Content.name.like(name.replace('*', '%')))

        if content_type is not None:
            query = query.filter(models.Content.content_tye == content_type)
        if min_id is not None:
            query = query.filter(models.Content.min_id <= min_id)
        if max_id is not None:
            query = query.filter(models.Content.max_id >= max_id)

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                if to_json:
                    rets.append(t.to_dict_json())
                else:
                    rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No match contents for (coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s): %s' %
                                  (coll_id, scope, name, content_type, min_id, max_id, error))
    except Exception as error:
        raise error


@read_session
def get_contents(scope=None, name=None, coll_id=None, status=None, to_json=False, session=None):
    """
    Get content or raise a NoObject exception.

    :param scope: The scope of the content data.
    :param name: The name of the content data.
    :param coll_id: list of Collection ids.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """

    try:
        if status is not None:
            if not isinstance(status, (tuple, list)):
                status = [status]
            if len(status) == 1:
                status = [status[0], status[0]]
        if coll_id is not None:
            if not isinstance(coll_id, (tuple, list)):
                coll_id = [coll_id]
            if len(coll_id) == 1:
                coll_id = [coll_id[0], coll_id[0]]

        query = session.query(models.Content)
        query = query.with_hint(models.Content, "INDEX(CONTENTS CONTENTS_ID_NAME_IDX)", 'oracle')

        if coll_id:
            query = query.filter(models.Content.coll_id.in_(coll_id))
        if scope:
            query = query.filter(models.Content.scope == scope)
        if name:
            query = query.filter(models.Content.name.like(name.replace('*', '%')))
        if status is not None:
            query = query.filter(models.Content.status.in_(status))

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                if to_json:
                    rets.append(t.to_dict_json())
                else:
                    rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (scope=%s, name=%s, coll_id=%s): %s' %
                                  (scope, name, coll_id, error))
    except Exception as error:
        raise error


@read_session
def get_contents_by_request_transform(request_id=None, transform_id=None, workload_id=None, status=None, status_updated=False, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param transform_id: transform id.
    :param workload_id: workload id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """

    try:
        if status is not None:
            if not isinstance(status, (tuple, list)):
                status = [status]

        query = session.query(models.Content)
        query = query.with_hint(models.Content, "INDEX(CONTENTS CONTENTS_REQ_TF_COLL_IDX)", 'oracle')
        if request_id:
            query = query.filter(models.Content.request_id == request_id)
        if transform_id:
            query = query.filter(models.Content.transform_id == transform_id)
        if workload_id:
            query = query.filter(models.Content.workload_id == workload_id)
        if status is not None:
            query = query.filter(models.Content.substatus.in_(status))
        if status_updated:
            query = query.filter(models.Content.status != models.Content.substatus)
        query = query.order_by(asc(models.Content.request_id), asc(models.Content.transform_id), asc(models.Content.map_id))

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (transform_id=%s): %s' %
                                  (transform_id, error))
    except Exception as error:
        raise error


@read_session
def get_contents_by_content_ids(content_ids, request_id=None, bulk_size=1000, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param content_ids: list of content id.
    :param workload_id: workload id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """
    try:
        if content_ids:
            if not isinstance(content_ids, (list, tuple)):
                content_ids = [content_ids]

        chunks = [content_ids[i:i + bulk_size] for i in range(0, len(content_ids), bulk_size)]
        ret = []
        for chunk in chunks:
            ret_chunk = get_contents_by_content_ids_real(chunk, request_id=request_id)
            ret = ret + ret_chunk
        return ret
    except Exception as error:
        raise error


@read_session
def get_contents_by_content_ids_real(content_ids, request_id=None, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param content_ids: list of content id.
    :param workload_id: workload id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """
    try:
        query = session.query(models.Content)
        query = query.with_hint(models.Content, "INDEX(CONTENTS CONTENTS_REQ_TF_COLL_IDX)", 'oracle')
        if request_id:
            query = query.filter(models.Content.request_id == request_id)
        query = query.filter(models.Content.content_id.in_(content_ids))
        ret = query.all()
        rets = [t.to_dict() for t in ret]
        return rets
    except Exception as error:
        raise error


@read_session
def get_input_contents(request_id, coll_id, name=None, to_json=False, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param coll_id: collection id.
    :param name: content name.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """

    try:
        query = session.query(models.Content)
        query = query.with_hint(models.Content, "INDEX(CONTENTS CONTENTS_REQ_TF_COLL_IDX)", 'oracle')
        query = query.filter(models.Content.request_id == request_id)
        query = query.filter(models.Content.coll_id == coll_id)

        if name:
            query = query.filter(models.Content.name == name)
        # query = query.filter(models.Content.content_relation_type == ContentRelationType.Input)
        query = query.order_by(asc(models.Content.map_id))

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                if to_json:
                    rets.append(t.to_dict_json())
                else:
                    rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (transform_id=%s, coll_id=%s, name=%s): %s' %
                                  (request_id, coll_id, name, error))
    except Exception as error:
        raise error


@read_session
def get_content_status_statistics(coll_id=None, session=None):
    """
    Get statistics group by status

    :param coll_id: Collection id.
    :param session: The database session in use.

    :returns: statistics group by status, as a dict.
    """
    try:
        query = session.query(models.Content.status, func.count(models.Content.content_id))
        query = query.with_hint(models.Content, "INDEX(CONTENTS CONTENTS_ID_NAME_IDX)", 'oracle')
        if coll_id:
            query = query.filter(models.Content.coll_id == coll_id)
        query = query.group_by(models.Content.status)
        tmp = query.all()
        rets = {}
        if tmp:
            for status, count in tmp:
                rets[status] = count
        return rets
    except Exception as error:
        raise error


@transactional_session
def update_content(content_id, parameters, session=None):
    """
    update a content.

    :param content_id: the content id.
    :param parameters: A dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        parameters['updated_at'] = datetime.datetime.utcnow()

        session.query(models.Content).filter_by(content_id=content_id)\
               .update(parameters, synchronize_session=False)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content %s cannot be found: %s' % (content_id, error))


@transactional_session
def update_contents(parameters, session=None):
    """
    update contents.

    :param parameters: list of dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        for parameter in parameters:
            parameter['updated_at'] = datetime.datetime.utcnow()

        session.bulk_update_mappings(models.Content, parameters)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content cannot be found: %s' % (error))


@transactional_session
def update_dep_contents(request_id, content_dep_ids, status, bulk_size=1000, session=None):
    """
    update dependency contents.

    :param content_dep_ids: list of content dependency id.
    :param status: Content status.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        params = {'substatus': status}
        chunks = [content_dep_ids[i:i + bulk_size] for i in range(0, len(content_dep_ids), bulk_size)]
        for chunk in chunks:
            session.query(models.Content).with_hint(models.Content, "INDEX(CONTENTS CONTENTS_DEP_IDX)")\
                   .filter(models.Content.request_id == request_id)\
                   .filter(models.Content.content_id.in_(chunk))\
                   .update(params, synchronize_session=False)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content cannot be found: %s' % (error))


@transactional_session
def delete_content(content_id=None, session=None):
    """
    delete a content.

    :param content_id: The id of the content.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.
    """
    try:
        session.query(models.Content).filter_by(content_id=content_id).delete()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content %s cannot be found: %s' % (content_id, error))


def get_contents_ext_items():
    default_params = {'pandaID': None, 'jobDefinitionID': None, 'schedulerID': None,
                      'pilotID': None, 'creationTime': None, 'modificationTime': None,
                      'startTime': None, 'endTime': None, 'prodSourceLabel': None,
                      'prodUserID': None, 'assignedPriority': None, 'currentPriority': None,
                      'attemptNr': None, 'maxAttempt': None, 'maxCpuCount': None,
                      'maxCpuUnit': None, 'maxDiskCount': None, 'maxDiskUnit': None,
                      'minRamCount': None, 'maxRamUnit': None, 'cpuConsumptionTime': None,
                      'cpuConsumptionUnit': None, 'jobStatus': None, 'jobName': None,
                      'transExitCode': None, 'pilotErrorCode': None, 'pilotErrorDiag': None,
                      'exeErrorCode': None, 'exeErrorDiag': None, 'supErrorCode': None,
                      'supErrorDiag': None, 'ddmErrorCode': None, 'ddmErrorDiag': None,
                      'brokerageErrorCode': None, 'brokerageErrorDiag': None,
                      'jobDispatcherErrorCode': None, 'jobDispatcherErrorDiag': None,
                      'taskBufferErrorCode': None, 'taskBufferErrorDiag': None,
                      'computingSite': None, 'computingElement': None,
                      'grid': None, 'cloud': None, 'cpuConversion': None, 'taskID': None,
                      'vo': None, 'pilotTiming': None, 'workingGroup': None,
                      'processingType': None, 'prodUserName': None, 'coreCount': None,
                      'nInputFiles': None, 'reqID': None, 'jediTaskID': None,
                      'actualCoreCount': None, 'maxRSS': None, 'maxVMEM': None,
                      'maxSWAP': None, 'maxPSS': None, 'avgRSS': None, 'avgVMEM': None,
                      'avgSWAP': None, 'avgPSS': None, 'maxWalltime': None, 'diskIO': None,
                      'failedAttempt': None, 'hs06': None, 'hs06sec': None,
                      'memory_leak': None, 'memory_leak_x2': None, 'job_label': None}
    return default_params


def get_contents_ext_maps():
    default_params = {'panda_id': 'PandaID', 'job_definition_id': 'jobDefinitionID', 'scheduler_id': 'schedulerID',
                      'pilot_id': 'pilotID', 'creation_time': 'creationTime', 'modification_time': 'modificationTime',
                      'start_time': 'startTime', 'end_time': 'endTime', 'prod_source_label': 'prodSourceLabel',
                      'prod_user_id': 'prodUserID', 'assigned_priority': 'assignedPriority', 'current_priority': 'currentPriority',
                      'attempt_nr': 'attemptNr', 'max_attempt': 'maxAttempt', 'max_cpu_count': 'maxCpuCount',
                      'max_cpu_unit': 'maxCpuUnit', 'max_disk_count': 'maxDiskCount', 'max_disk_unit': 'maxDiskUnit',
                      'min_ram_count': 'minRamCount', 'min_ram_unit': 'minRamUnit', 'cpu_consumption_time': 'cpuConsumptionTime',
                      'cpu_consumption_unit': 'cpuConsumptionUnit', 'job_status': 'jobStatus', 'job_name': 'jobName',
                      'trans_exit_code': 'transExitCode', 'pilot_error_code': 'pilotErrorCode', 'pilot_error_diag': 'pilotErrorDiag',
                      'exe_error_code': 'exeErrorCode', 'exe_error_diag': 'exeErrorDiag', 'sup_error_code': 'supErrorCode',
                      'sup_error_diag': 'supErrorDiag', 'ddm_error_code': 'ddmErrorCode', 'ddm_error_diag': 'ddmErrorDiag',
                      'brokerage_error_cdode': 'brokerageErrorCode', 'brokerage_error_diag': 'brokerageErrorDiag',
                      'job_dispatcher_error_code': 'jobDispatcherErrorCode', 'job_dispatcher_error_diag': 'jobDispatcherErrorDiag',
                      'task_buffer_error_code': 'taskBufferErrorCode', 'task_buffer_error_diag': 'taskBufferErrorDiag',
                      'computing_site': 'computingSite', 'computing_element': 'computingElement',
                      'grid': 'grid', 'cloud': 'cloud', 'cpu_conversion': 'cpuConversion', 'task_id': 'taskID',
                      'vo': 'VO', 'pilot_timing': 'pilotTiming', 'working_group': 'workingGroup',
                      'processing_type': 'processingType', 'prod_user_name': 'prodUserName', 'core_count': 'coreCount',
                      'n_input_files': 'nInputFiles', 'req_id': 'reqID', 'jedi_task_id': 'jediTaskID',
                      'actual_core_count': 'actualCoreCount', 'max_rss': 'maxRSS', 'max_vmem': 'maxVMEM',
                      'max_swap': 'maxSWAP', 'max_pss': 'maxPSS', 'avg_rss': 'avgRSS', 'avg_vmem': 'avgVMEM',
                      'avg_swap': 'avgSWAP', 'avg_pss': 'avgPSS', 'max_walltime': 'maxWalltime', 'disk_io': 'diskIO',
                      'failed_attempt': 'failedAttempt', 'hs06': 'hs06', 'hs06sec': 'hs06sec',
                      'memory_leak': 'memory_leak', 'memory_leak_x2': 'memory_leak_x2', 'job_label': 'job_label'}
    return default_params


@transactional_session
def add_contents_update(contents, bulk_size=10000, session=None):
    """
    Add contents update.

    :param contents: dict of contents.
    :param session: session.

    :raises DuplicatedObject: If a collection with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: content ids.
    """
    sub_params = [contents[i:i + bulk_size] for i in range(0, len(contents), bulk_size)]

    try:
        for sub_param in sub_params:
            session.bulk_insert_mappings(models.Content_update, sub_param)
        content_ids = [None for _ in range(len(contents))]
        return content_ids
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Duplicated objects: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def delete_contents_update(session=None):
    """
    delete a content.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.
    """
    try:
        session.query(models.Content_update).delete()
    except Exception as error:
        raise exceptions.NoObject('Content_update deletion error: %s' % (error))


@transactional_session
def add_contents_ext(contents, bulk_size=10000, session=None):
    """
    Add contents ext.

    :param contents: dict of contents.
    :param session: session.

    :raises DuplicatedObject: If a collection with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: content ids.
    """
    default_params = get_contents_ext_items()
    default_params['status'] = ContentStatus.New

    for content in contents:
        for key in default_params:
            if key not in content:
                content[key] = default_params[key]

    sub_params = [contents[i:i + bulk_size] for i in range(0, len(contents), bulk_size)]

    try:
        for sub_param in sub_params:
            session.bulk_insert_mappings(models.Content_ext, sub_param)
        content_ids = [None for _ in range(len(contents))]
        return content_ids
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Duplicated objects: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def update_contents_ext(parameters, session=None):
    """
    update contents ext.

    :param parameters: list of dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        session.bulk_update_mappings(models.Content_ext, parameters)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content cannot be found: %s' % (error))


@read_session
def get_contents_ext(request_id=None, transform_id=None, workload_id=None, coll_id=None, status=None, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param transform_id: transform id.
    :param workload_id: workload id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of contents.
    """

    try:
        if status is not None:
            if not isinstance(status, (tuple, list)):
                status = [status]

        query = session.query(models.Content_ext)
        query = query.with_hint(models.Content_ext, "INDEX(CONTENTS_EXT CONTENTS_EXT_RTF_IDX)")
        if request_id:
            query = query.filter(models.Content_ext.request_id == request_id)
        if transform_id:
            query = query.filter(models.Content_ext.transform_id == transform_id)
        if workload_id:
            query = query.filter(models.Content_ext.workload_id == workload_id)
        if coll_id:
            query = query.filter(models.Content_ext.coll_id == coll_id)
        if status is not None:
            query = query.filter(models.Content_ext.status.in_(status))
        query = query.order_by(asc(models.Content_ext.request_id), asc(models.Content_ext.transform_id), asc(models.Content_ext.map_id))

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (transform_id=%s): %s' %
                                  (transform_id, error))
    except Exception as error:
        raise error


@read_session
def get_contents_ext_ids(request_id=None, transform_id=None, workload_id=None, coll_id=None, status=None, session=None):
    """
    Get content or raise a NoObject exception.

    :param request_id: request id.
    :param transform_id: transform id.
    :param workload_id: workload id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of content ids.
    """

    try:
        if status is not None:
            if not isinstance(status, (tuple, list)):
                status = [status]

        query = session.query(models.Content_ext.request_id,
                              models.Content_ext.transform_id,
                              models.Content_ext.workload_id,
                              models.Content_ext.coll_id,
                              models.Content_ext.content_id,
                              models.Content_ext.panda_id,
                              models.Content_ext.status)
        query = query.with_hint(models.Content_ext, "INDEX(CONTENTS_EXT CONTENTS_EXT_RTF_IDX)")
        if request_id:
            query = query.filter(models.Content_ext.request_id == request_id)
        if transform_id:
            query = query.filter(models.Content_ext.transform_id == transform_id)
        if workload_id:
            query = query.filter(models.Content_ext.workload_id == workload_id)
        if coll_id:
            query = query.filter(models.Content_ext.coll_id == coll_id)
        if status is not None:
            query = query.filter(models.Content_ext.status.in_(status))
        query = query.order_by(asc(models.Content_ext.request_id), asc(models.Content_ext.transform_id), asc(models.Content_ext.map_id))

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (transform_id=%s): %s' %
                                  (transform_id, error))
    except Exception as error:
        raise error


def combine_contents_ext(contents, contents_ext, with_status_name=False):
    contents_ext_map = {}
    for content in contents_ext:
        contents_ext_map[content['content_id']] = content

    rets = []
    for content in contents:
        content_id = content['content_id']
        if content_id in contents_ext_map:
            ret = contents_ext_map[content_id]
        else:
            ret = {'content_id': content_id}
        if with_status_name:
            ret['status'] = content['status'].name
        else:
            ret['status'] = content['status']
        ret['scope'] = content['scope']
        ret['name'] = content['name']

        rets.append(ret)
    return rets
