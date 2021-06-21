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
Class of base plugin
"""

from idds.common import exceptions
from idds.common.plugin.plugin_base import PluginBase


class ProcessingPluginBase(PluginBase):
    def __init__(self, poll_time_period=2, **kwargs):
        super(ProcessingPluginBase, self).__init__(**kwargs)
        self.poll_time_period = int(poll_time_period)

    def __call__(self, **kwargs):
        return exceptions.NotImplementedException(self.get_class_name())
