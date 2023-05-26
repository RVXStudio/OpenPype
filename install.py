import os
import shutil
import sys
import importlib
import platform


root = os.path.dirname(os.path.abspath(__file__))

build_dir = os.path.join(root, 'build')

for bd in os.listdir(build_dir):
    if bd.startswith('exe.'):
        the_build = bd
        break
else:
    print("NO build dir found!")
    the_build = None

if the_build is not None:
    version_file = os.path.join(build_dir, the_build, 'openpype', 'version.py')
    spec = importlib.util.spec_from_file_location('op_version', version_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules['op_version'] = module
    spec.loader.exec_module(module)

    the_version = module.__version__

    platform_name = the_build.split('.')[1].split('-')[0]

    if platform.system() == 'Linux':
        # we on lin
        dest_dir = f'/pipeline/AstralProjection/apps/ayon/builds/ayon_{the_version}_{platform_name}'
    else:
        dest_dir = f'X:/AstralProjection/apps/ayon/builds/ayon_{the_version}_{platform_name}'

    src_dir = os.path.join(build_dir, the_build)

    os.makedirs(dest_dir, exist_ok=True)
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)



if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--build')
    args = parser.parse_args()