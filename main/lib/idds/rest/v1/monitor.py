#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019

import datetime
from collections import OrderedDict
from traceback import format_exc

from flask import Blueprint

from idds.common import exceptions
from idds.common.constants import HTTP_STATUS_CODE
from idds.core.requests import get_requests
from idds.rest.v1.controller import IDDSController


class Monitor(IDDSController):
    """ Monitor """

    def get_month_list(self, start, end):
        return list(OrderedDict(((start + datetime.timedelta(_)).strftime(r"%Y-%m"), None) for _ in range(max(1, (end - start).days))).keys())

    def get_requests(self, request_id, workload_id, with_detail=False, with_processing=False, with_metadata=False):
        rets = []
        # reqs = get_requests(request_id=request_id, workload_id=workload_id, to_json=True)
        reqs = get_requests(request_id=request_id, workload_id=workload_id, with_detail=with_detail, with_processing=with_processing, with_metadata=False)
        for req in reqs:
            if with_processing:
                ret = {'request_id': req['request_id'],
                       'workload_id': req['workload_id'],
                       'processing_id': req['processing_id'],
                       'processing_status': req['processing_status'].name if req['processing_status'] else req['processing_status'],
                       'processing_created_at': req['processing_created_at'],
                       'processing_updated_at': req['processing_updated_at'],
                       'processing_finished_at': req['processing_finished_at']
                       }
            elif with_detail:
                ret = {'request_id': req['request_id'],
                       'transform_id': req['transform_id'],
                       'workload_id': req['workload_id'],
                       'transform_workload_id': req['transform_workload_id'],
                       'transform_type': req['transform_type'].name if req['transform_type'] else req['transform_type'],
                       'output_coll_scope': req['output_coll_scope'],
                       'output_coll_name': req['output_coll_name'],
                       'transform_status': req['transform_status'].name if req['transform_status'] else req['transform_status'],
                       'transform_created_at': req['transform_created_at'],
                       'transform_updated_at': req['transform_updated_at'],
                       'transform_finished_at': req['transform_finished_at'],
                       'input_total_files': req['input_total_files'] if req['input_total_files'] else 0,
                       'input_coll_bytes': req['input_coll_bytes'] if req['input_coll_bytes'] else 0,
                       'input_processed_files': req['input_processed_files'] if req['input_processed_files'] else 0,
                       'input_processing_files': req['input_processing_files'] if req['input_processing_files'] else 0,
                       'output_total_files': req['output_total_files'] if req['output_total_files'] else 0,
                       'output_coll_bytes': req['output_coll_bytes'] if req['output_coll_bytes'] else 0,
                       'output_processed_files': req['output_processed_files'] if req['output_processed_files'] else 0,
                       'output_processing_files': req['output_processing_files'] if req['output_processing_files'] else 0,
                       'errors': req['errors']
                       }
            else:
                ret = {'request_id': req['request_id'],
                       'workload_id': req['workload_id'],
                       'status': req['status'].name if req['status'] else req['status'],
                       'created_at': req['created_at'],
                       'updated_at': req['updated_at']
                       }
            rets.append(ret)
        return rets

    def get(self, request_id, workload_id, with_detail='false', with_processing='false', with_metadata='false'):
        """ Get details about a specific Request with given id.
        HTTP Success:
            200 OK
        HTTP Error:
            404 Not Found
            500 InternalError
        :returns: dictionary of an request.
        """

        try:
            if request_id == 'null':
                request_id = None
            if workload_id == 'null':
                workload_id = None
            if with_detail and with_detail.lower() in ['true']:
                with_detail = True
            else:
                with_detail = False
            if with_processing and with_processing.lower() in ['true']:
                with_processing = True
            else:
                with_processing = False
            if with_metadata and with_metadata.lower() in ['true']:
                with_metadata = True
            else:
                with_metadata = False

            rets = self.get_requests(request_id=request_id, workload_id=workload_id, with_detail=with_detail, with_processing=with_processing, with_metadata=False)
        except exceptions.NoObject as error:
            return self.generate_http_response(HTTP_STATUS_CODE.NotFound, exc_cls=error.__class__.__name__, exc_msg=error)
        except exceptions.IDDSException as error:
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=error.__class__.__name__, exc_msg=error)
        except Exception as error:
            print(error)
            print(format_exc())
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=exceptions.CoreException.__name__, exc_msg=error)

        return self.generate_http_response(HTTP_STATUS_CODE.OK, data=rets)

    def post_test(self):
        import pprint
        pprint.pprint(self.get_request())
        pprint.pprint(self.get_request().endpoint)
        pprint.pprint(self.get_request().url_rule)


class MonitorRequest(Monitor):
    """ Monitor Request """

    def get(self, request_id, workload_id):
        """ Get details about a specific Request with given id.
        HTTP Success:
            200 OK
        HTTP Error:
            404 Not Found
            500 InternalError
        :returns: dictionary of an request.
        """

        try:
            if request_id == 'null':
                request_id = None
            if workload_id == 'null':
                workload_id = None

            rets = self.get_requests(request_id=request_id, workload_id=workload_id, with_detail=False, with_processing=False, with_metadata=False)
            status_dict = {'Total': {}}
            min_time, max_time = None, None
            for ret in rets:
                if ret['status'] not in status_dict:
                    status_dict[ret['status']] = {}
                if min_time is None or ret['updated_at'] < min_time:
                    min_time = ret['updated_at']
                if max_time is None or ret['updated_at'] > max_time:
                    max_time = ret['updated_at']

            month_list = self.get_month_list(min_time, max_time)
            for key in status_dict:
                for m in month_list:
                    status_dict[key][m] = 0

            for ret in rets:
                m_time = ret['updated_at'].strftime(r"%Y-%m")
                status_dict['Total'][m_time] += 1
                status_dict[ret['status']][m_time] += 1

            status_dict_acc = {}
            for key in status_dict:
                status_dict_acc[key] = {}
                for i in range(len(month_list)):
                    if i == 0:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]]
                    else:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]] + status_dict_acc[key][month_list[i - 1]]
            ret_status = {'total': len(rets), 'month_status': status_dict, 'month_acc_status': status_dict_acc}
        except exceptions.NoObject as error:
            return self.generate_http_response(HTTP_STATUS_CODE.NotFound, exc_cls=error.__class__.__name__, exc_msg=error)
        except exceptions.IDDSException as error:
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=error.__class__.__name__, exc_msg=error)
        except Exception as error:
            print(error)
            print(format_exc())
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=exceptions.CoreException.__name__, exc_msg=error)

        return self.generate_http_response(HTTP_STATUS_CODE.OK, data=ret_status)


class MonitorTransform(Monitor):
    """ Monitor Transform """

    def get(self, request_id, workload_id):
        """ Get details about a specific Request with given id.
        HTTP Success:
            200 OK
        HTTP Error:
            404 Not Found
            500 InternalError
        :returns: dictionary of an request.
        """

        try:
            if request_id == 'null':
                request_id = None
            if workload_id == 'null':
                workload_id = None

            rets = self.get_requests(request_id=request_id, workload_id=workload_id, with_detail=True, with_processing=False, with_metadata=False)
            status_dict = {'Total': {}}
            status_dict_by_type = {}
            processed_files, processed_bytes = {}, {}
            processed_files_by_type, processed_bytes_by_type = {}, {}
            min_time, max_time = None, None
            total_files, total_bytes = 0, 0
            for ret in rets:
                if ret['transform_status'] and ret['transform_status'] not in status_dict:
                    status_dict[ret['transform_status']] = {}
                if ret['transform_type'] and ret['transform_type'] not in status_dict_by_type:
                    status_dict_by_type[ret['transform_type']] = {}
                    processed_files_by_type[ret['transform_type']] = {}
                    processed_bytes_by_type[ret['transform_type']] = {}
                if ret['transform_updated_at'] and (min_time is None or ret['transform_updated_at'] < min_time):
                    min_time = ret['transform_updated_at']
                if ret['transform_updated_at'] and (max_time is None or ret['transform_updated_at'] > max_time):
                    max_time = ret['transform_updated_at']

            month_list = self.get_month_list(min_time, max_time)
            for key in status_dict:
                processed_files[key] = {}
                processed_bytes[key] = {}
                for t_type in status_dict_by_type:
                    status_dict_by_type[t_type][key] = {}
                    processed_files_by_type[t_type][key] = {}
                    processed_bytes_by_type[t_type][key] = {}
                for m in month_list:
                    status_dict[key][m] = 0
                    processed_files[key][m] = 0
                    processed_bytes[key][m] = 0
                    for t_type in status_dict_by_type:
                        status_dict_by_type[t_type][key][m] = 0
                        processed_files_by_type[t_type][key][m] = 0
                        processed_bytes_by_type[t_type][key][m] = 0

            for ret in rets:
                if not ret['transform_updated_at']:
                    continue
                m_time = ret['transform_updated_at'].strftime(r"%Y-%m")
                status_dict['Total'][m_time] += 1
                status_dict[ret['transform_status']][m_time] += 1
                processed_files[ret['transform_status']][m_time] += ret['output_processed_files']
                # processed_bytes[ret['transform_status']][m_time] += ret['output_coll_bytes']
                # output_coll_bytes is not filled, need to be fixed on the server
                processed_bytes[ret['transform_status']][m_time] += ret['input_coll_bytes']
                processed_files['Total'][m_time] += ret['output_processed_files']
                # processed_bytes['Total'][m_time] += ret['output_coll_bytes']
                processed_bytes['Total'][m_time] += ret['input_coll_bytes']

                total_files += ret['output_processed_files']
                total_bytes += ret['output_coll_bytes']
                total_bytes += ret['input_coll_bytes']

                t_type = ret['transform_type']
                status_dict_by_type[t_type][ret['transform_status']][m_time] += 1
                processed_files_by_type[t_type][ret['transform_status']][m_time] += ret['output_processed_files']
                # processed_bytes_by_type[t_type][ret['transform_status']][m_time] += ret['output_coll_bytes']
                processed_bytes_by_type[t_type][ret['transform_status']][m_time] += ret['input_coll_bytes']
                status_dict_by_type[t_type]['Total'][m_time] += 1
                processed_files_by_type[t_type]['Total'][m_time] += ret['output_processed_files']
                # processed_bytes_by_type[t_type]['Total'][m_time] += ret['output_coll_bytes']
                processed_bytes_by_type[t_type]['Total'][m_time] += ret['input_coll_bytes']

            status_dict_acc = {}
            processed_files_acc, processed_bytes_acc = {}, {}
            status_dict_by_type_acc = {}
            processed_files_by_type_acc = {}
            processed_bytes_by_type_acc = {}
            for t_type in status_dict_by_type:
                status_dict_by_type_acc[t_type] = {}
                processed_files_by_type_acc[t_type] = {}
                processed_bytes_by_type_acc[t_type] = {}
            for key in status_dict:
                status_dict_acc[key] = {}
                processed_files_acc[key] = {}
                processed_bytes_acc[key] = {}
                for t_type in status_dict_by_type:
                    status_dict_by_type_acc[t_type][key] = {}
                    processed_files_by_type_acc[t_type][key] = {}
                    processed_bytes_by_type_acc[t_type][key] = {}

                for i in range(len(month_list)):
                    if i == 0:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]]
                        processed_files_acc[key][month_list[i]] = processed_files[key][month_list[i]]
                        processed_bytes_acc[key][month_list[i]] = processed_bytes[key][month_list[i]]
                        for t_type in status_dict_by_type_acc:
                            status_dict_by_type_acc[t_type][key][month_list[i]] = status_dict_by_type[t_type][key][month_list[i]]
                            processed_files_by_type_acc[t_type][key][month_list[i]] = processed_files_by_type[t_type][key][month_list[i]]
                            processed_bytes_by_type_acc[t_type][key][month_list[i]] = processed_bytes_by_type[t_type][key][month_list[i]]
                    else:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]] + status_dict_acc[key][month_list[i - 1]]
                        processed_files_acc[key][month_list[i]] = processed_files[key][month_list[i]] + processed_files_acc[key][month_list[i - 1]]
                        processed_bytes_acc[key][month_list[i]] = processed_bytes[key][month_list[i]] + processed_bytes_acc[key][month_list[i - 1]]
                        for t_type in status_dict_by_type_acc:
                            status_dict_by_type_acc[t_type][key][month_list[i]] = status_dict_by_type[t_type][key][month_list[i]] + status_dict_by_type_acc[t_type][key][month_list[i - 1]]
                            processed_files_by_type_acc[t_type][key][month_list[i]] = processed_files_by_type[t_type][key][month_list[i]] + processed_files_by_type_acc[t_type][key][month_list[i - 1]]
                            processed_bytes_by_type_acc[t_type][key][month_list[i]] = processed_bytes_by_type[t_type][key][month_list[i]] + processed_bytes_by_type_acc[t_type][key][month_list[i - 1]]
            ret_status = {'total': len(rets),
                          'total_files': total_files,
                          'total_bytes': total_bytes,
                          'month_status': status_dict,
                          'month_acc_status': status_dict_acc,
                          'month_processed_files': processed_files,
                          'month_acc_processed_files': processed_files_acc,
                          'month_processed_bytes': processed_bytes,
                          'month_acc_processed_bytes': processed_bytes_acc,
                          'month_status_dict_by_type': status_dict_by_type,
                          'month_acc_status_dict_by_type': status_dict_by_type_acc,
                          'month_processed_files_by_type': processed_files_by_type,
                          'month_acc_processed_files_by_type': processed_files_by_type_acc,
                          'month_processed_bytes_by_type': processed_bytes_by_type,
                          'month_acc_processed_bytes_by_type': processed_bytes_by_type_acc
                          }
        except exceptions.NoObject as error:
            return self.generate_http_response(HTTP_STATUS_CODE.NotFound, exc_cls=error.__class__.__name__, exc_msg=error)
        except exceptions.IDDSException as error:
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=error.__class__.__name__, exc_msg=error)
        except Exception as error:
            print(error)
            print(format_exc())
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=exceptions.CoreException.__name__, exc_msg=error)

        return self.generate_http_response(HTTP_STATUS_CODE.OK, data=ret_status)


class MonitorProcessing(Monitor):
    """ Monitor Processing """

    def get(self, request_id, workload_id):
        """ Get details about a specific Request with given id.
        HTTP Success:
            200 OK
        HTTP Error:
            404 Not Found
            500 InternalError
        :returns: dictionary of an request.
        """

        try:
            if request_id == 'null':
                request_id = None
            if workload_id == 'null':
                workload_id = None

            rets = self.get_requests(request_id=request_id, workload_id=workload_id, with_detail=False, with_processing=True, with_metadata=False)
            status_dict = {'Total': {}}
            min_time, max_time = None, None
            for ret in rets:
                if ret['processing_status'] and ret['processing_status'] not in status_dict:
                    status_dict[ret['processing_status']] = {}
                if ret['processing_updated_at'] and (min_time is None or ret['processing_updated_at'] < min_time):
                    min_time = ret['processing_updated_at']
                if ret['processing_updated_at'] and (max_time is None or ret['processing_updated_at'] > max_time):
                    max_time = ret['processing_updated_at']

            month_list = self.get_month_list(min_time, max_time)
            for key in status_dict:
                for m in month_list:
                    status_dict[key][m] = 0

            for ret in rets:
                if ret['processing_updated_at']:
                    m_time = ret['processing_updated_at'].strftime(r"%Y-%m")
                    status_dict['Total'][m_time] += 1
                    status_dict[ret['processing_status']][m_time] += 1

            status_dict_acc = {}
            for key in status_dict:
                status_dict_acc[key] = {}
                for i in range(len(month_list)):
                    if i == 0:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]]
                    else:
                        status_dict_acc[key][month_list[i]] = status_dict[key][month_list[i]] + status_dict_acc[key][month_list[i - 1]]
            ret_status = {'total': len(rets), 'month_status': status_dict, 'month_acc_status': status_dict_acc}
        except exceptions.NoObject as error:
            return self.generate_http_response(HTTP_STATUS_CODE.NotFound, exc_cls=error.__class__.__name__, exc_msg=error)
        except exceptions.IDDSException as error:
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=error.__class__.__name__, exc_msg=error)
        except Exception as error:
            print(error)
            print(format_exc())
            return self.generate_http_response(HTTP_STATUS_CODE.InternalError, exc_cls=exceptions.CoreException.__name__, exc_msg=error)

        return self.generate_http_response(HTTP_STATUS_CODE.OK, data=ret_status)


"""----------------------
   Web service url maps
----------------------"""


def get_blueprint():
    bp = Blueprint('monitor', __name__)

    monitor_view = Monitor.as_view('monitor')
    bp.add_url_rule('/monitor/<request_id>/<workload_id>/<with_detail>/<with_processing>', view_func=monitor_view, methods=['get', ])

    monitor_request_view = MonitorRequest.as_view('monitor_request')
    bp.add_url_rule('/monitor_request/<request_id>/<workload_id>', view_func=monitor_request_view, methods=['get', ])

    monitor_transform_view = MonitorTransform.as_view('monitor_transform')
    bp.add_url_rule('/monitor_transform/<request_id>/<workload_id>', view_func=monitor_transform_view, methods=['get', ])

    monitor_processing_view = MonitorProcessing.as_view('monitor_processing')
    bp.add_url_rule('/monitor_processing/<request_id>/<workload_id>', view_func=monitor_processing_view, methods=['get', ])

    return bp
