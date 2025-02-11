#  Copyright (c) Meta Platforms, Inc. and affiliates.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import unittest
from unittest.mock import patch

from aitemplate.backend.profiler_cache import ProfileCacheDB

from aitemplate.compiler import compile_model, ops
from aitemplate.frontend import IntImm, Tensor
from aitemplate.testing import detect_target


class GemmProfilerCacheTestCase(unittest.TestCase):
    def _test(
        self,
        first_dim,
        logger,
        test_name="gemm_rcr",
        k=128,
        n=8,
    ):
        target = detect_target()

        X = Tensor(
            shape=[first_dim, k],
            dtype="float16",
            name="input_0",
            is_input=True,
        )
        W = Tensor(
            shape=[n, k],
            dtype="float16",
            name="input_1",
            is_input=True,
        )
        OP = ops.gemm_rcr()
        Y = OP(X, W)
        Y._attrs["name"] = "output_0"
        Y._attrs["is_output"] = True

        with self.assertLogs(
            logger=logger,
            level="INFO",
        ) as logs:
            compile_model(
                Y,
                target,
                "./tmp",
                test_name,
            )

        return "\n".join(logs.output)

    def _run_test(
        self,
        first_dim,
        test_name,
        logger,
    ):
        old_trick = os.environ.get("TRICK_CI_ENV", None)
        old_cache = os.environ.get("CACHE_DIR", None)
        try:
            os.environ["TRICK_CI_ENV"] = "1"
            os.environ["CACHE_DIR"] = f"/tmp/aitemplate/{test_name}"
            return self._test(
                first_dim=first_dim,
                logger=logger,
                test_name=test_name,
            )
        finally:
            if old_trick is not None:
                os.environ["TRICK_CI_ENV"] = old_trick
            else:
                os.environ.pop("TRICK_CI_ENV")
            if old_cache is not None:
                os.environ["CACHE_DIR"] = old_cache
            else:
                os.environ.pop("CACHE_DIR")

    def test_gemm_profiler_cache(self):
        first_dim = IntImm(4)
        test_name = "gemm_rcr_profiler_cache"
        logger = "aitemplate.compiler.transform.profile"

        run1_logs = self._run_test(
            first_dim=first_dim,
            test_name=test_name,
            logger=logger,
        )
        self.assertIn("generated 1 profilers", run1_logs)

        run2_logs = self._run_test(
            first_dim=first_dim,
            test_name=test_name,
            logger=logger,
        )
        self.assertIn("generated 0 profilers", run2_logs)

    def test_gemm_profiler_cache_versioning(self):
        first_dim = IntImm(4)
        test_name = "gemm_rcr_profiler_cache_versioning"
        logger = "aitemplate.backend.profiler_cache"
        cache_version_property = "gemm_cache_version"
        target_name = detect_target().name()

        with patch.object(
            target=ProfileCacheDB,
            attribute=cache_version_property,
            new=1,  # version
        ):
            run1_before_version_change_logs = self._run_test(
                first_dim=first_dim,
                test_name=test_name,
                logger=logger,
            )
            self.assertIn(
                f"table_name='{target_name}_gemm_1' does not exist in the db",
                run1_before_version_change_logs,
            )

            run2_before_version_change_logs = self._run_test(
                first_dim=first_dim,
                test_name=test_name,
                logger=logger,
            )
            self.assertIn(
                f"table_name='{target_name}_gemm_1' exists in the db",
                run2_before_version_change_logs,
            )

        with patch.object(
            target=ProfileCacheDB,
            attribute=cache_version_property,
            new=2,  # version
        ):
            run1_after_version_change_logs = self._run_test(
                first_dim=first_dim,
                test_name=test_name,
                logger=logger,
            )
            self.assertIn(
                f"table_name='{target_name}_gemm_2' does not exist in the db",
                run1_after_version_change_logs,
            )

            run2_after_version_change_logs = self._run_test(
                first_dim=first_dim,
                test_name=test_name,
                logger=logger,
            )
            self.assertIn(
                f"table_name='{target_name}_gemm_2' exists in the db",
                run2_after_version_change_logs,
            )
