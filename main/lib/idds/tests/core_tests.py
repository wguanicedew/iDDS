import sys

from idds.common.utils import json_dumps                 # noqa F401
from idds.common.constants import ContentStatus          # noqa F401
from idds.core.requests import get_requests              # noqa F401
from idds.core.messages import retrieve_messages         # noqa F401
from idds.core.transforms import get_transforms          # noqa F401
from idds.core.workprogress import get_workprogresses    # noqa F401
from idds.core.processings import get_processings        # noqa F401
from idds.core import transforms as core_transforms      # noqa F401


def show_works(req):
    workflow = req['processing_metadata']['workflow']
    print(workflow.independent_works)
    print(len(workflow.independent_works))
    print(workflow.works_template.keys())
    print(len(workflow.works_template.keys()))
    print(workflow.work_sequence.keys())
    print(len(workflow.work_sequence.keys()))
    print(workflow.works.keys())
    print(len(workflow.works.keys()))

    work_ids = []
    for i_id in workflow.works:
        work = workflow.works[i_id]
        print(i_id)
        print(work.work_name)
        print(work.task_name)
        print(work.work_id)
        work_ids.append(work.work_id)
    print(work_ids)


reqs = get_requests(request_id=268, with_detail=False)
for req in reqs:
    # print(req['request_id'])
    # print(rets)
    # print(json_dumps(req, sort_keys=True, indent=4))
    # show_works(req)
    pass

# sys.exit(0)

# reqs = get_requests()
# print(len(reqs))
"""
for req in reqs:
    if req['request_id'] == 113:
        # print(req)
        # print(req['request_metadata']['workflow'].to_dict())
        # print(json_dumps(req, sort_keys=True, indent=4))
        pass
"""

tfs = get_transforms(transform_id=53550)
for tf in tfs:
    # print(tf)
    # print(tf['transform_metadata']['work'].to_dict())
    print(json_dumps(tf, sort_keys=True, indent=4))
    pass

sys.exit(0)

msgs = retrieve_messages()
for msg in msgs:
    # if msg['msg_id'] in [323720]:
    # if True:
    # if msg['request_id'] in [208]:
    if msg['transform_id'] in [1186]:
        # print(msg)
        # print(msg['msg_content'])
        pass
    pass

wps = get_workprogresses()
for wp in wps:
    if wp['workprogress_id'] == 79:
        # print(json_dumps(wp, sort_keys=True, indent=4))
        pass

prs = get_processings()
for pr in prs:
    if pr['request_id'] == 91:
        # print(json_dumps(pr, sort_keys=True, indent=4))
        pass

to_release_inputs = [{'request_id': 248,
                      'coll_id': 3425,
                      'name': 'shared_pipecheck_20210407T110240Z.qgraph',
                      'status': ContentStatus.Available,
                      'substatus': ContentStatus.Available}]
# updated_contents = core_transforms.release_inputs(to_release_inputs)
# print(updated_contents)
