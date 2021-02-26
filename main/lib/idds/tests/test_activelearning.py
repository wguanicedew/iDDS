#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019 - 2021


"""
Test client.
"""
import re
import time
# import traceback

# from idds.client.client import Client
from idds.client.clientmanager import ClientManager
# from idds.common.constants import RequestType, RequestStatus
from idds.common.utils import get_rest_host, run_command
# from idds.common.utils import json_dumps
# from idds.tests.common import get_example_real_tape_stagein_request
# from idds.tests.common import get_example_prodsys2_tape_stagein_request

# from idds.workflow.work import Work, Parameter, WorkStatus
from idds.workflow.workflow import Condition, Workflow
# from idds.workflow.workflow import Workflow
# from idds.atlas.workflow.atlasstageinwork import ATLASStageinWork
from idds.atlas.workflow.atlaspandawork import ATLASPandaWork
from idds.atlas.workflow.atlasactuatorwork import ATLASActuatorWork


def get_task_id(output, error):
    m = re.search('jediTaskID=(\d+)', output + error)  # noqa W605
    task_id = int(m.group(1))
    return task_id


def submit_processing_task():
    cmd = "cd /afs/cern.ch/user/w/wguan/workdisk/iDDS/test/activelearning/hepexcursion/grid; prun --exec 'python simplescript.py 0.5 0.5 200 output.json' --outDS user.wguan.altest123456  --outputs output.json --nJobs=10"
    status, output, error = run_command(cmd)
    """
    print("status:")
    print(status)
    print("output:")
    print(output)
    print("error:")
    print(error)

    status:
    0
    output:

    error:
    INFO : gathering files under /afs/cern.ch/work/w/wguan/iDDS/test/activelearning/hepexcursion/grid
    INFO : upload source files
    INFO : submit user.wguan.altest1234/
    INFO : succeeded. new jediTaskID=23752996
    """
    if status == 0:
        task_id = get_task_id(output, error)
        return task_id
    else:
        raise Exception(output + error)


def test_panda_work(panda_task_id):
    cmd_to_arguments = {'arguments': 'python simplescript.py 0.5 0.5 200',
                        'parameters': 'python simplescript.py {m1} {m2} {nevents}',
                        'outDS': 'user.wguan.altest123456'}
    work = ATLASPandaWork(panda_task_id=panda_task_id, cmd_to_arguments=cmd_to_arguments)
    work.initialize_work()
    print(work.__class__.__name__)
    print('sandbox: %s' % work.sandbox)
    print('output_collections: %s' % str(work.get_output_collections()))

    print("new work")
    test_work = work.generate_work_from_template()
    test_work.initialize_work()
    test_work.set_parameters({'m1': 0.5, 'm2': 0.5, 'nevents': 100})
    test_work.parse_arguments()
    # print(json_dumps(test_work, sort_keys=True, indent=4))
    # print('output_collections: %s' % str(test_work.get_output_collections()))
    # print(json_dumps(test_work, sort_keys=True, indent=4))

    # from pandatools import Client
    # Client.getJediTaskDetails(taskDict,fullFlag,withTaskInfo,verbose=False)
    # ret = Client.getJediTaskDetails({'jediTaskID': panda_task_id},False,True)
    # print(ret)


def get_workflow(panda_task_id):
    cmd_to_arguments = {'arguments': 'python simplescript.py 0.5 0.5 200',
                        'parameters': 'python simplescript.py {m1} {m2} {nevents}',
                        'outDS': 'user.wguan.altest123456'}
    work = ATLASPandaWork(panda_task_id=panda_task_id, cmd_to_arguments=cmd_to_arguments)

    # it's needed to parse the panda task parameter information, for example output dataset name, for the next task.
    # if the information is not needed, you don't need to run it manually. iDDS will call it interally to parse the information.
    work.initialize_work()

    work_output_coll = work.get_output_collections()[0]

    input_coll = {'scope': work_output_coll['scope'],
                  'name': work_output_coll['name'],
                  'coll_metadata': {'force_close': True}}
    output_coll = {'scope': work_output_coll['scope'],
                   'name': work_output_coll['name'] + "." + str(int(time.time()))}

    # acutator = ATLASActuatorWork(executable='python', arguments='merge.py {output_json} {events} {dataset}/{filename}',
    acutator = ATLASActuatorWork(executable='python', arguments='merge.py {output_json} {events} {dataset}',
                                 parameters={'output_json': 'merge.json',
                                             'events': 200,
                                             'dataset': '{scope}:{name}'.format(**input_coll),
                                             'filename': 'output*.json'},
                                 sandbox=work.sandbox, primary_input_collection=input_coll,
                                 output_collections=output_coll, output_json='merge.json')
    wf = Workflow()
    # because the two tasks are in a loop. It's good to set which one to start.
    wf.add_work(work)
    wf.add_work(acutator)
    cond = Condition(work.is_finished, current_work=work, true_work=acutator, false_work=None)
    wf.add_condition(cond)
    cond1 = Condition(acutator.generate_new_task, current_work=acutator, true_work=work, false_work=None)
    wf.add_condition(cond1)

    # because the two works are in a loop, they are not independent. This call is needed to tell which one to start.
    # otherwise idds will use the first one to start.
    wf.add_initial_works(work)

    # work.set_workflow(wf)
    return wf


if __name__ == '__main__':
    host = get_rest_host()
    # panda_task_id = submit_processing_task()
    # panda_task_id = 23752996
    # panda_task_id = 23810059
    panda_task_id = 23818866
    print(panda_task_id)
    test_panda_work(panda_task_id)
    workflow = get_workflow(panda_task_id)
    wm = ClientManager(host=host)
    request_id = wm.submit(workflow)
    print(request_id)