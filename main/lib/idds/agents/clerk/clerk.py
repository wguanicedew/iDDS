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
import traceback
try:
    # python 3
    from queue import Queue
except ImportError:
    # Python 2
    from Queue import Queue

from idds.common import exceptions
from idds.common.constants import (Sections, RequestStatus, RequestLocking,
                                   TransformStatus)
from idds.common.utils import setup_logging
from idds.core import (requests as core_requests,
                       transforms as core_transforms)
from idds.agents.common.baseagent import BaseAgent

setup_logging(__name__)


class Clerk(BaseAgent):
    """
    Clerk works to process requests and converts requests to transforms.
    """

    def __init__(self, num_threads=1, poll_time_period=10, retrieve_bulk_size=10, **kwargs):
        super(Clerk, self).__init__(num_threads=num_threads, **kwargs)
        self.poll_time_period = int(poll_time_period)
        self.retrieve_bulk_size = int(retrieve_bulk_size)
        self.config_section = Sections.Clerk

        self.new_task_queue = Queue()
        self.new_output_queue = Queue()
        self.running_task_queue = Queue()
        self.running_output_queue = Queue()

    def show_queue_size(self):
        q_str = "new queue size: %s, new output queue size: %s" % (self.new_task_queue.qsize(),
                                                                   self.new_output_queue.qsize())
        q_str += "running queue size: %s, running output queue size: %s" % (self.running_task_queue.qsize(),
                                                                            self.running_output_queue.qsize())
        self.logger.info(q_str)

    def get_new_requests(self):
        """
        Get new requests to process
        """
        try:
            # req_status = [RequestStatus.TransformingOpen]
            # reqs_open = core_requests.get_requests_by_status_type(status=req_status, time_period=3600)
            # self.logger.info("Main thread get %s TransformingOpen requests to process" % len(reqs_open))

            if self.new_task_queue.qsize() > 0 or self.new_output_queue.qsize() > 0:
                return []

            self.show_queue_size()

            req_status = [RequestStatus.New, RequestStatus.Extend]
            reqs_new = core_requests.get_requests_by_status_type(status=req_status, locking=True,
                                                                 bulk_size=self.retrieve_bulk_size)

            self.logger.debug("Main thread get %s [New+Extend] requests to process" % len(reqs_new))
            if reqs_new:
                self.logger.info("Main thread get %s [New+Extend] requests to process" % len(reqs_new))

            return reqs_new
        except exceptions.DatabaseException as ex:
            if 'ORA-00060' in str(ex):
                self.logger.warn("(cx_Oracle.DatabaseError) ORA-00060: deadlock detected while waiting for resource")
            else:
                raise ex
        return []

    def process_new_request(self, req):
        try:
            workflow = req['request_metadata']['workflow']

            wf = workflow.copy()
            works = wf.get_new_works()
            transforms = []
            for work in works:
                new_work = work.copy()
                new_work.add_proxy(wf.get_proxy())
                new_work.create_processing()
                transform = {'request_id': req['request_id'],
                             'workload_id': req['workload_id'],
                             'transform_type': work.get_work_type(),
                             'transform_tag': work.get_work_tag(),
                             'priority': req['priority'],
                             'status': TransformStatus.New,
                             'retries': 0,
                             'expired_at': req['expired_at'],
                             'transform_metadata': {'internal_id': new_work.get_internal_id(),
                                                    'template_work_id': new_work.get_template_work_id(),
                                                    'sequence_id': new_work.get_sequence_id(),
                                                    'work_name': new_work.get_work_name(),
                                                    'work': new_work,
                                                    'original_work': work}
                             'running_metadata': {'work_data': new_work.get_running_data()}
                             # 'collections': related_collections
                             }
                transforms.append(transform)
            self.logger.info("Processing request(%s): new transforms: %s" % (req['request_id'],
                                                                             str(transforms)))
            processing_metadata = req['processing_metadata']
            processing_metadata = {'workflow_data': wf.get_running_data()}

            ret_req = {'request_id': req['request_id'],
                       'parameters': {'status': RequestStatus.Transforming,
                                      'locking': RequestLocking.Idle,
                                      'processing_metadata': processing_metadata},
                       'new_transforms': transforms}
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            ret_req = {'request_id': req['request_id'],
                       'parameters': {'status': RequestStatus.Failed,
                                      'locking': RequestLocking.Idle,
                                      'errors': {'msg': '%s: %s' % (ex, traceback.format_exc())}}}
        return ret_req

    def process_new_requests(self):
        """
        Process new request
        """
        ret = []
        while not self.new_task_queue.empty():
            try:
                req = self.new_task_queue.get()
                if req:
                    self.logger.info("Main thread processing new requst: %s" % req)
                    ret_req = self.process_new_request(req)
                    if ret_req:
                        # ret.append(ret_req)
                        self.new_output_queue.put(ret_req)
            except Exception as ex:
                self.logger.error(ex)
                self.logger.error(traceback.format_exc())
        return ret

    def finish_new_requests(self):
        while not self.new_output_queue.empty():
            try:
                req = self.new_output_queue.get()
                self.logger.info("Main thread finished processing requst: %s" % req)
                req['parameters']['locking'] = RequestLocking.Idle

                if 'new_transforms' in req:
                    new_transforms = req['new_transforms']
                else:
                    new_transforms = []

                if 'update_transforms' in req:
                    update_transforms = req['update_transforms']
                else:
                    update_transforms = []

                core_requests.update_request_with_transforms(req['request_id'], req['parameters'],
                                                             new_transforms=new_transforms,
                                                             update_transforms=update_transforms)
            except Exception as ex:
                self.logger.error(ex)
                self.logger.error(traceback.format_exc())

    def get_running_requests(self):
        """
        Get running requests
        """
        try:
            if self.running_task_queue.qsize() > 0 or self.running_output_queue.qsize() > 0:
                return []

            self.show_queue_size()

            req_status = [RequestStatus.Transforming, RequestStatus.ToCancel, RequestStatus.Cancelling,
                          RequestStatus.ToSuspend, RequestStatus.Suspending,
                          RequestStatus.Resuming]
            reqs = core_requests.get_requests_by_status_type(status=req_status, time_period=self.poll_time_period,
                                                             locking=True, bulk_size=self.retrieve_bulk_size)

            req_status = [RequestStatus.ToResume]
            reqs_1 = core_requests.get_requests_by_status_type(status=req_status, time_period=self.poll_time_period,
                                                               locking=True, by_substatus=True, bulk_size=self.retrieve_bulk_size)

            reqs = reqs + reqs_1

            self.logger.debug("Main thread get %s Transforming requests to running" % len(reqs))
            if reqs:
                self.logger.info("Main thread get %s Transforming requests to running" % len(reqs))
            return reqs
        except exceptions.DatabaseException as ex:
            if 'ORA-00060' in str(ex):
                self.logger.warn("(cx_Oracle.DatabaseError) ORA-00060: deadlock detected while waiting for resource")
            else:
                raise ex
        return []

    def process_running_request_real(self, req):
        """
        process running request
        """
        self.logger.info("process_running_request: request_id: %s" % req['request_id'])
        processing_metadata = req['processing_metadata']
        if 'workflow_data' in processing_metadata:
            # for new version
            wf_data = processing_metadata['workflow_data']
            workflow = req['request_metadata']['workflow']
            wf = workflow.copy()
            wf.load_running_data(wf_data)
        else:
            # for old version
            wf = processing_metadata['workflow']
            del processing_metadata['workflow']

        new_transforms = []
        if req['status'] in [RequestStatus.Transforming]:
            # new works
            works = wf.get_new_works()
            for work in works:
                new_work = work.copy()
                new_work.add_proxy(wf.get_proxy())
                new_transform = {'request_id': req['request_id'],
                                 'workload_id': req['workload_id'],
                                 'transform_type': work.get_work_type(),
                                 'transform_tag': work.get_work_tag(),
                                 'priority': req['priority'],
                                 'status': TransformStatus.New,
                                 'retries': 0,
                                 'expired_at': req['expired_at'],
                                 'transform_metadata': {'internal_id': new_work.get_internal_id(),
                                                        'template_work_id': new_work.get_template_work_id(),
                                                        'sequence_id': new_work.get_sequence_id(),
                                                        'work_name': new_work.get_work_name(),
                                                        'work': new_work,
                                                        'original_work': work}
                                 'running_metadata': {'work_data': new_work.get_running_data()}
                                 # 'collections': related_collections
                                 }
                new_transforms.append(new_transform)
            self.logger.info("Processing request(%s): new transforms: %s" % (req['request_id'],
                                                                             str(new_transforms)))
        # current works
        works = wf.get_current_works()
        # print(works)
        for work in works:
            # print(work.get_work_id())
            tf = core_transforms.get_transform(transform_id=work.get_work_id())
            transform_work = tf['transform_metadata']['work']
            # work_status = WorkStatus(tf['status'].value)
            # work.set_status(work_status)
            work.sync_work_data(status=tf['status'], substatus=tf['substatus'], work=transform_work)

        if wf.is_terminated():
            if wf.is_finished():
                req_status = RequestStatus.Finished
            elif wf.is_subfinished():
                req_status = RequestStatus.SubFinished
            elif wf.is_failed():
                req_status = RequestStatus.Failed
            elif wf.is_expired():
                req_status = RequestStatus.Expired
            elif wf.is_cancelled():
                req_status = RequestStatus.Cancelled
            elif wf.is_suspended():
                req_status = RequestStatus.Suspended
            else:
                req_status = RequestStatus.Failed
            req_msg = wf.get_terminated_msg()
        else:
            if req['status'] in [RequestStatus.ToSuspend, RequestStatus.Suspending]:
                req_status = RequestStatus.Suspending
            elif req['status'] in [RequestStatus.ToCancel, RequestStatus.Cancelling]:
                req_status = RequestStatus.Cancelling
            else:
                req_status = RequestStatus.Transforming
            req_msg = None

        processing_metadata['workflow_data'] = wf.get_running_data()

        parameters = {'status': req_status,
                      'locking': RequestLocking.Idle,
                      'processing_metadata': processing_metadata,
                      'errors': {'msg': req_msg}}
        ret = {'request_id': req['request_id'],
               'parameters': parameters,
               'new_transforms': new_transforms}   # 'update_transforms': update_transforms}
        return ret

    def process_running_request(self, req):
        """
        process running request
        """
        try:
            ret_req = self.process_running_request_real(req)
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            ret_req = {'request_id': req['request_id'],
                       'parameters': {'status': RequestStatus.Failed,
                                      'locking': RequestLocking.Idle,
                                      'errors': {'msg': '%s: %s' % (ex, traceback.format_exc())}}}
        return ret_req

    def process_operating_request_real(self, req):
        """
        process ToCancel/ToSuspend/ToResume request
        """
        if req['substatus'] == RequestStatus.ToCancel:
            tf_status = TransformStatus.ToCancel
            req_status = RequestStatus.Cancelling
        if req['substatus'] == RequestStatus.ToSuspend:
            tf_status = TransformStatus.ToSuspend
            req_status = RequestStatus.Suspending
        if req['substatus'] == RequestStatus.ToResume:
            tf_status = TransformStatus.ToResume
            req_status = RequestStatus.Resuming

        processing_metadata = req['processing_metadata']

        if req['substatus'] == RequestStatus.ToResume:
            if 'workflow_data' in processing_metadata:
                # for new version
                wf_data = processing_metadata['workflow_data']
                workflow = req['request_metadata']['workflow']
                wf = workflow.copy()
                wf.load_running_data(wf_data)
            else:
                # for old version
                wf = processing_metadata['workflow']
                del processing_metadata['workflow']

            wf.resume_works()

        if 'operations' not in processing_metadata:
            processing_metadata['operations'] = []
        processing_metadata['operations'].append({'status': req['substatus'], 'time': datetime.datetime.utcnow()})

        tfs = core_transforms.get_transforms(request_id=req['request_id'])
        tfs_status = {}
        for tf in tfs:
            # if tf['status'] not in [RequestStatus.Finished, RequestStatus.SubFinished,
            #                         RequestStatus.Failed, RequestStatus.Cancelling,
            #                         RequestStatus.Cancelled, RequestStatus.Suspending,
            #                         RequestStatus.Suspended]:
            tfs_status[tf['transform_id']] = {'substatus': tf_status}

        processing_metadata['workflow_data'] = wf.get_running_data()

        ret_req = {'request_id': req['request_id'],
                   'parameters': {'status': req_status,
                                  'substatus': req_status,
                                  'processing_metadata': req['processing_metadata'],
                                  'locking': RequestLocking.Idle},
                   'update_transforms': tfs_status
                   }
        return ret_req

    def process_operating_request(self, req):
        """
        process ToCancel/ToSuspend/ToResume request
        """
        try:
            ret_req = self.process_operating_request_real(req)
        except Exception as ex:
            self.logger.error(ex)
            self.logger.error(traceback.format_exc())
            ret_req = {'request_id': req['request_id'],
                       'parameters': {'status': RequestStatus.Failed,
                                      'locking': RequestLocking.Idle,
                                      'errors': {'msg': '%s: %s' % (ex, traceback.format_exc())}}}
        return ret_req

    def process_running_requests(self):
        """
        Process running request
        """
        ret = []
        while not self.running_task_queue.empty():
            try:
                req = self.running_task_queue.get()
                if req:
                    if req['substatus'] in [RequestStatus.ToCancel, RequestStatus.ToSuspend, RequestStatus.ToResume]:
                        self.logger.info("Main thread processing operating requst: %s" % req)
                        ret_req = self.process_operating_request(req)
                    elif req['status'] in [RequestStatus.Transforming, RequestStatus.Cancelling, RequestStatus.Suspending, RequestStatus.Resuming]:
                        self.logger.info("Main thread processing running requst: %s" % req)
                        ret_req = self.process_running_request(req)

                    if ret_req:
                        # ret.append(ret_req)
                        self.running_output_queue.put(ret_req)
            except Exception as ex:
                self.logger.error(ex)
                self.logger.error(traceback.format_exc())
        return ret

    def finish_running_requests(self):
        while not self.running_output_queue.empty():
            req = self.running_output_queue.get()
            self.logger.info("finish_running_requests: req: %s" % req)
            req['parameters']['locking'] = RequestLocking.Idle

            if 'new_transforms' in req:
                new_transforms = req['new_transforms']
            else:
                new_transforms = []

            if 'update_transforms' in req:
                update_transforms = req['update_transforms']
            else:
                update_transforms = []

            core_requests.update_request_with_transforms(req['request_id'], req['parameters'],
                                                         new_transforms=new_transforms,
                                                         update_transforms=update_transforms)

    def clean_locks(self):
        self.logger.info("clean locking")
        core_requests.clean_locking()

    def run(self):
        """
        Main run function.
        """
        try:
            self.logger.info("Starting main thread")

            self.load_plugins()

            self.add_default_tasks()

            task = self.create_task(task_func=self.get_new_requests, task_output_queue=self.new_task_queue, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
            self.add_task(task)
            for _ in range(self.num_threads):
                # task = self.create_task(task_func=self.process_new_requests, task_output_queue=self.new_output_queue, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
                task = self.create_task(task_func=self.process_new_requests, task_output_queue=None, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
                self.add_task(task)
            task = self.create_task(task_func=self.finish_new_requests, task_output_queue=None, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
            self.add_task(task)

            task = self.create_task(task_func=self.get_running_requests, task_output_queue=self.running_task_queue, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
            self.add_task(task)
            for _ in range(self.num_threads):
                # task = self.create_task(task_func=self.process_running_requests, task_output_queue=self.running_output_queue, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
                task = self.create_task(task_func=self.process_running_requests, task_output_queue=None, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
                self.add_task(task)
            task = self.create_task(task_func=self.finish_running_requests, task_output_queue=None, task_args=tuple(), task_kwargs={}, delay_time=1, priority=1)
            self.add_task(task)

            task = self.create_task(task_func=self.clean_locks, task_output_queue=None, task_args=tuple(), task_kwargs={}, delay_time=1800, priority=1)
            self.add_task(task)

            self.execute()
        except KeyboardInterrupt:
            self.stop()


if __name__ == '__main__':
    agent = Clerk()
    agent()
