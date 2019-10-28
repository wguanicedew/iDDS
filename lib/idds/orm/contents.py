#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019


"""
operations related to Requests.
"""

import datetime
import json

import sqlalchemy
from sqlalchemy import BigInteger, Integer
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.sql import text, outparam

from idds.common import exceptions
from idds.common.constants import ContentType, ContentStatus
from idds.orm.base.session import read_session, transactional_session
from idds.orm.base.utils import row2dict


@transactional_session
def add_content(coll_id, scope, name, min_id, max_id, content_type=ContentType.File, status=ContentStatus.New,
                content_size=0, md5=None, adler32=None, processing_id=None, storage_id=None, retries=0,
                path=None, expired_at=None, collcontent_metadata=None, returning_id=False, session=None):
    """
    Add a content.

    :param coll_id: collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.
    :param status: content status.
    :param content_size: The size of the content.
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
    if isinstance(content_type, ContentType):
        content_type = content_type.value
    if isinstance(status, ContentStatus):
        status = status.value
    if collcontent_metadata:
        collcontent_metadata = json.dumps(collcontent_metadata)

    if returning_id:
        insert_coll_sql = """insert into atlas_idds.collections_content(coll_id, scope, name, min_id, max_id, content_type,
                                                                       status, content_size, md5, adler32, processing_id,
                                                                       storage_id, retries, path, expired_at,
                                                                       collcontent_metadata)
                             values(:coll_id, :scope, :name, :min_id, :max_id, :content_type, :status, :content_size,
                                    :md5, :adler32, :processing_id, :storage_id, :retries, :path, :expired_at,
                                    :collcontent_metadata) RETURNING content_id into :content_id
                          """
        stmt = text(insert_coll_sql)
        stmt = stmt.bindparams(outparam("content_id", type_=BigInteger().with_variant(Integer, "sqlite")))
    else:
        insert_coll_sql = """insert into atlas_idds.collections_content(coll_id, scope, name, min_id, max_id, content_type,
                                                                       status, content_size, md5, adler32, processing_id,
                                                                       storage_id, retries, path, expired_at,
                                                                       collcontent_metadata)
                             values(:coll_id, :scope, :name, :min_id, :max_id, :content_type, :status, :content_size,
                                    :md5, :adler32, :processing_id, :storage_id, :retries, :path, :expired_at,
                                    :collcontent_metadata)
                          """
        stmt = text(insert_coll_sql)

    try:
        content_id = None
        if returning_id:
            ret = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name, 'min_id': min_id, 'max_id': max_id,
                                         'content_type': content_type, 'status': status, 'content_size': content_size, 'md5': md5,
                                         'adler32': adler32, 'processing_id': processing_id, 'storage_id': storage_id,
                                         'retries': retries, 'path': path, 'created_at': datetime.datetime.utcnow(),
                                         'updated_at': datetime.datetime.utcnow(), 'expired_at': expired_at,
                                         'collcontent_metadata': collcontent_metadata, 'content_id': content_id})
            content_id = ret.out_parameters['content_id'][0]
        else:
            ret = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name, 'min_id': min_id, 'max_id': max_id,
                                         'content_type': content_type, 'status': status, 'content_size': content_size, 'md5': md5,
                                         'adler32': adler32, 'processing_id': processing_id, 'storage_id': storage_id,
                                         'retries': retries, 'path': path, 'created_at': datetime.datetime.utcnow(),
                                         'updated_at': datetime.datetime.utcnow(), 'expired_at': expired_at,
                                         'collcontent_metadata': collcontent_metadata})

        return content_id
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Content coll_id:scope:name(%s:%s:%s) already exists!: %s' %
                                          (coll_id, scope, name, error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def add_contents(contents, returning_id=False, bulk_size=100, session=None):
    """
    Add contents.

    :param contents: dict of contents.
    :param returning_id: whether to return id.
    :param session: session.

    :raises DuplicatedObject: If a collection with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: content id.
    """
    default_params = {'coll_id': None, 'scope': None, 'name': None, 'min_id': None, 'max_id': None,
                      'content_type': ContentType.File, 'status': ContentStatus.New,
                      'content_size': 0, 'md5': None, 'adler32': None, 'processing_id': None,
                      'storage_id': None, 'retries': 0, 'path': None,
                      'expired_at': datetime.datetime.utcnow() + datetime.timedelta(days=30),
                      'collcontent_metadata': None}

    if returning_id:
        insert_coll_sql = """insert into atlas_idds.collections_content(coll_id, scope, name, min_id, max_id, content_type,
                                                                       status, content_size, md5, adler32, processing_id,
                                                                       storage_id, retries, path, expired_at,
                                                                       collcontent_metadata)
                             values(:coll_id, :scope, :name, :min_id, :max_id, :content_type, :status, :content_size,
                                    :md5, :adler32, :processing_id, :storage_id, :retries, :path, :expired_at,
                                    :collcontent_metadata) RETURNING content_id into :content_id
                          """
        stmt = text(insert_coll_sql)
        stmt = stmt.bindparams(outparam("content_id", type_=BigInteger().with_variant(Integer, "sqlite")))
    else:
        insert_coll_sql = """insert into atlas_idds.collections_content(coll_id, scope, name, min_id, max_id, content_type,
                                                                       status, content_size, md5, adler32, processing_id,
                                                                       storage_id, retries, path, expired_at,
                                                                       collcontent_metadata)
                             values(:coll_id, :scope, :name, :min_id, :max_id, :content_type, :status, :content_size,
                                    :md5, :adler32, :processing_id, :storage_id, :retries, :path, :expired_at,
                                    :collcontent_metadata)
                          """
        stmt = text(insert_coll_sql)

    params = []
    for content in contents:
        param = {}
        for key in default_params:
            if key in content:
                param[key] = content[key]
            else:
                param[key] = default_params[key]

        if isinstance(param['content_type'], ContentType):
            param['content_type'] = param['content_type'].value
        if isinstance(param['status'], ContentStatus):
            param['status'] = param['status'].value
        if param['collcontent_metadata']:
            param['collcontent_metadata'] = json.dumps(param['collcontent_metadata'])
        params.append(param)

    sub_params = [params[i:i + bulk_size] for i in range(0, len(params), bulk_size)]

    try:
        content_ids = None
        if returning_id:
            content_ids = []
            for sub_param in sub_params:
                content_id = None
                sub_param['content_id'] = content_id
                ret = session.execute(stmt, sub_param)
                content_ids.extend(ret.out_parameters['content_id'])
        else:
            for sub_param in sub_params:
                ret = session.execute(stmt, sub_param)
            content_ids = [None for _ in range(len(params))]
        return content_ids
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Duplicated objects: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@read_session
def get_content_id(coll_id, scope, name, content_type=ContentType.File, min_id=None, max_id=None, session=None):
    """
    Get content id or raise a NoObject exception.

    :param coll_id: collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: Content id.
    """

    try:
        if isinstance(content_type, ContentType):
            content_type = content_type.value
        if content_type == ContentType.File.value:
            select = """select content_id from atlas_idds.collections_content where coll_id=:coll_id and
                        scope=:scope and name=:name and content_type=:content_type"""
            stmt = text(select)
            result = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name,
                                            'content_type': content_type})
        else:
            select = """select content_id from atlas_idds.collections_content where coll_id=:coll_id and
                        scope=:scope and name=:name and content_type=:content_type and min_id=:min_id and
                        max_id=:max_id"""
            stmt = text(select)
            result = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name,
                                            'content_type': content_type, 'min_id': min_id, 'max_id': max_id})

        content_id = result.fetchone()

        if content_id is None:
            raise exceptions.NoObject('content(coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s) cannot be found' %
                                      (coll_id, scope, name, content_type, min_id, max_id))
        content_id = content_id[0]
        return content_id
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('content(coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s) cannot be found: %s' %
                                  (coll_id, scope, name, content_type, min_id, max_id, error))
    except Exception as error:
        raise error


@read_session
def get_content(content_id=None, coll_id=None, scope=None, name=None, content_type=ContentType.File, min_id=None, max_id=None, session=None):
    """
    Get content or raise a NoObject exception.

    :param content_id: Content id.
    :param coll_id: Collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: Content.
    """

    try:
        if not content_id:
            content_id = get_content_id(coll_id=coll_id, scope=scope, name=name, content_type=content_type, min_id=min_id, max_id=max_id, session=session)
        select = """select * from atlas_idds.collections_content where content_id=:content_id"""
        stmt = text(select)
        result = session.execute(stmt, {'content_id': content_id})
        content = result.fetchone()

        if content is None:
            raise exceptions.NoObject('content(content_id: %s, coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s) cannot be found' %
                                      (content_id, coll_id, scope, name, content_type, min_id, max_id))

        content = row2dict(content)
        if content['content_type'] is not None:
            content['content_type'] = ContentType(content['content_type'])
        if content['status'] is not None:
            content['status'] = ContentStatus(content['status'])
        if content['collcontent_metadata']:
            content['collcontent_metadata'] = json.loads(content['collcontent_metadata'])

        return content
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('content(content_id: %s, coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s) cannot be found: %s' %
                                  (content_id, coll_id, scope, name, content_type, min_id, max_id, error))
    except Exception as error:
        raise error


@read_session
def get_match_contents(coll_id, scope, name, content_type=None, min_id=None, max_id=None, session=None):
    """
    Get contents which matches the query or raise a NoObject exception.

    :param coll_id: collection id.
    :param scope: The scope of the request data.
    :param name: The name of the request data.
    :param min_id: The minimal id of the content.
    :param max_id: The maximal id of the content.
    :param content_type: The type of the content.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: list of Content ids.
    """

    try:
        if min_id is None and max_id is None:
            content_type = ContentType.File.value
        if content_type is not None and isinstance(content_type, ContentType):
            content_type = content_type.value

        if content_type is not None and content_type == ContentType.File.value:
            select = """select * from atlas_idds.collections_content where coll_id=:coll_id and
                        scope=:scope and name=:name and content_type=:content_type"""
            stmt = text(select)
            result = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name,
                                            'content_type': content_type})
        else:
            select = """select * from atlas_idds.collections_content where coll_id=:coll_id and
                        scope=:scope and name=:name and min_id<=:min_id and max_id>=:max_id"""
            stmt = text(select)
            result = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': name,
                                            'min_id': min_id, 'max_id': max_id})

        contents = result.fetchall()
        rets = []
        for content in contents:
            content = row2dict(content)
            if content['content_type'] is not None:
                content['content_type'] = ContentType(content['content_type'])
            if content['status'] is not None:
                content['status'] = ContentStatus(content['status'])
            if content['collcontent_metadata']:
                content['collcontent_metadata'] = json.loads(content['collcontent_metadata'])
            rets.append(content)
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No match contents for (coll_id: %s, scope: %s, name: %s, content_type: %s, min_id: %s, max_id: %s): %s' %
                                  (coll_id, scope, name, content_type, min_id, max_id, error))
    except Exception as error:
        raise error


@read_session
def get_contents(scope=None, name=None, coll_id=None, session=None):
    """
    Get content or raise a NoObject exception.

    :param scope: The scope of the content data.
    :param name: The name of the content data.
    :param coll_id: Collection id.

    :param session: The database session in use.

    :raises NoObject: If no content is founded.

    :returns: Content.
    """

    try:
        if scope and name:
            if coll_id:
                select = """select * from atlas_idds.collections_content where coll_id=:coll_id and
                            scope=:scope and name like :name"""
                stmt = text(select)
                result = session.execute(stmt, {'coll_id': coll_id, 'scope': scope, 'name': '%' + name + '%'})
            else:
                select = """select * from atlas_idds.collections_content where scope=:scope and name like :name"""
                stmt = text(select)
                result = session.execute(stmt, {'scope': scope, 'name': '%' + name + '%'})
        else:
            if coll_id:
                select = """select * from atlas_idds.collections_content where coll_id=:coll_id"""
                stmt = text(select)
                result = session.execute(stmt, {'coll_id': coll_id})
            else:
                raise exceptions.WrongParameterException("Both (scope:%s and name:%s) and coll_id:%s are not fully provided")

        contents = result.fetchall()
        rets = []
        for content in contents:
            content = row2dict(content)
            if content['content_type'] is not None:
                content['content_type'] = ContentType(content['content_type'])
            if content['status'] is not None:
                content['status'] = ContentStatus(content['status'])
            if content['collcontent_metadata']:
                content['collcontent_metadata'] = json.loads(content['collcontent_metadata'])
            rets.append(content)
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No record can be found with (scope=%s, name=%s, coll_id=%s): %s' %
                                  (scope, name, coll_id, error))
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
        if 'content_type' in parameters and isinstance(parameters['content_type'], ContentType):
            parameters['content_type'] = parameters['content_type'].value
        if 'status' in parameters and isinstance(parameters['status'], ContentStatus):
            parameters['status'] = parameters['status'].value
        if 'collcontent_metadata' in parameters:
            parameters['collcontent_metadata'] = json.dumps(parameters['collcontent_metadata'])

        parameters['updated_at'] = datetime.datetime.utcnow()

        update = "update atlas_idds.collections_content set "
        for key in parameters.keys():
            update += key + "=:" + key + ","
        update = update[:-1]
        update += " where content_id=:content_id"

        stmt = text(update)
        parameters['content_id'] = content_id
        session.execute(stmt, parameters)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content %s cannot be found: %s' % (content_id, error))


@transactional_session
def update_contents(parameters, session=None):
    """
    updatecontents.

    :param parameters: list of dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        keys = ['coll_id', 'scope', 'name', 'min_id', 'max_id', 'status', 'path']
        update = """update atlas_idds.collections_content set path=:path, updated_at=:updated_at, status=:status
                    where coll_id=:coll_id and scope=:scope and name=:name and min_id=:min_id and max_id=:max_id"""

        contents = []
        for parameter in parameters:
            content = {}
            for key in keys:
                if key in parameter:
                    content[key] = parameter[key]
                else:
                    content[key] = None
            if content['status'] is not None and isinstance(content['status'], ContentStatus):
                content['status'] = content['status'].value
            content['updated_at'] = datetime.datetime.utcnow()
            contents.append(content)

        stmt = text(update)
        session.execute(stmt, contents)
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
        delete = "delete from atlas_idds.collections_content where content_id=:content_id"
        stmt = text(delete)
        session.execute(stmt, {'content_id': content_id})
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Content %s cannot be found: %s' % (content_id, error))
