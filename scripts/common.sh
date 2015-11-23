# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# author: jorr@google.com (John Orr)
#
# Common library shared by all shell scripts in this package.
#

# Force shell to fail on any errors.
set -e

GCB_GIT_URL=https://code.google.com/p/course-builder/
GCB_REPO_NAME=course-builder
GCB_GIT_REV=7aebc8574de7

MODULE_NAME=learning_analytics

clean_examples_folder() {
  pushd examples
  rm -rf $GCB_REPO_NAME
  rm -rf coursebuilder
  popd
}

checkout_course_builder() {
  pushd examples
  git clone $GCB_GIT_URL $GCB_REPO_NAME
  cd $GCB_REPO_NAME
  git checkout $GCB_GIT_REV
  mv coursebuilder ..
  cd ..
  rm -rf $GCB_REPO_NAME
  popd
}

install_module() {
  ln -s ../../../src examples/coursebuilder/modules/$MODULE_NAME
  ln -s ../../../../tests examples/coursebuilder/tests/ext/$MODULE_NAME
}

patch_course_builder() {
  patch -p0 < scripts/patches/coursebuilder.patch
}

require_course_builder() {
  if [ ! -d examples/coursebuilder ]; then
    checkout_course_builder
    install_module
    patch_course_builder
  fi
}

install_run_requirements() {
  require_course_builder
}