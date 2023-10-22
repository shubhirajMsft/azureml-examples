# imports
import os
import json
import glob
import argparse
import hashlib
import random
import string
import yaml

# define constants
EXCLUDED_JOBS = ["java", "spark-job-component", "storage_pe", "user-assigned-identity"]
# TODO: Re-include these below endpoints and deployments when the workflow generation code supports substituting vars in .yaml files.
EXCLUDED_ENDPOINTS = [
    "1-uai-create-endpoint",
    "1-sai-create-endpoint",
    "tfserving-endpoint",
]
EXCLUDED_DEPLOYMENTS = [
    "minimal-multimodel-deployment",
    "minimal-single-model-conda-in-dockerfile-deployment",
    "mlflow-deployment",
    "r-deployment",
    "torchserve-deployment",
    "triton-cc-deployment",
    "2-sai-deployment",
    "kubernetes-green-deployment",
]
EXCLUDED_RESOURCES = [
    "workspace",
    "datastore",
    "vm-attach",
    "instance",
    "connections",
    "compute/cluster-user-identity",
    "compute/attached-spark",
    "compute/attached-spark-system-identity",
    "compute/attached-spark-user-identity",
    "registry",
]
EXCLUDED_ASSETS = ["conda-yamls", "mlflow-models"]
EXCLUDED_SCHEDULES = []
EXCLUDED_SCRIPTS = [
    "setup",
    "cleanup",
    "run-job",
    "run-pipeline-job-with-registry-components",
    "deploy-custom-container-multimodel-minimal",
    "run-pipeline-jobs",
]
READONLY_HEADER = "# This code is autogenerated.\
\n# Code is generated by running custom script: python3 readme.py\
\n# Any manual changes to this file may cause incorrect behavior.\
\n# Any manual changes will be overwritten if the code is regenerated.\n"
CREDENTIALS = "${{secrets.AZUREML_CREDENTIALS}}"
BRANCH = "main"  # default - do not change
# Duplicate name in working directory during checkout
# https://github.com/actions/checkout/issues/739
GITHUB_WORKSPACE = "${{ github.workspace }}"
GITHUB_CONCURRENCY_GROUP = (
    "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}"
)
# BRANCH = "sdk-preview"  # this should be deleted when this branch is merged to main
hours_between_runs = 12


# define functions
def main(args):
    # get list of notebooks
    notebooks = sorted(glob.glob("**/*.ipynb", recursive=True))

    # make all notebooks consistent
    modify_notebooks(notebooks)

    # get list of jobs
    jobs = sorted(glob.glob("jobs/**/*job*.yml", recursive=True))
    jobs += sorted(glob.glob("jobs/basics/*.yml", recursive=False))
    jobs += sorted(glob.glob("jobs/*/basics/**/*job*.yml", recursive=True))
    jobs += sorted(glob.glob("jobs/pipelines/**/*pipeline*.yml", recursive=True))
    jobs += sorted(glob.glob("jobs/spark/*.yml", recursive=False))
    jobs += sorted(
        glob.glob("jobs/automl-standalone-jobs/**/cli-automl-*.yml", recursive=True)
    )
    jobs += sorted(
        glob.glob("jobs/pipelines-with-components/**/*pipeline*.yml", recursive=True)
    )
    jobs += sorted(
        glob.glob("jobs/automl-standalone-jobs/**/*cli-automl*.yml", recursive=True)
    )
    jobs += sorted(glob.glob("responsible-ai/**/cli-*.yml", recursive=True))
    jobs += sorted(glob.glob("jobs/parallel/**/*pipeline*.yml", recursive=True))
    jobs = [
        job.replace(".yml", "")
        for job in jobs
        if not any(excluded in job for excluded in EXCLUDED_JOBS)
    ]

    jobs_using_registry_components = sorted(
        glob.glob(
            "jobs/pipelines-with-components/basics/**/*pipeline*.yml", recursive=True
        )
    )
    jobs_using_registry_components = [
        job.replace(".yml", "")
        for job in jobs_using_registry_components
        if not any(excluded in job.replace(os.sep, "/") for excluded in EXCLUDED_JOBS)
    ]

    # get list of endpoints
    endpoints = sorted(glob.glob("endpoints/**/*endpoint.yml", recursive=True))
    endpoints = [
        endpoint.replace(".yml", "")
        for endpoint in endpoints
        if not any(
            excluded in endpoint.replace(os.sep, "/") for excluded in EXCLUDED_ENDPOINTS
        )
    ]

    # get list of resources
    resources = sorted(glob.glob("resources/**/*.yml", recursive=True))
    resources = [
        resource.replace(".yml", "")
        for resource in resources
        if not any(
            excluded in resource.replace(os.sep, "/") for excluded in EXCLUDED_RESOURCES
        )
    ]

    # get list of assets
    assets = sorted(glob.glob("assets/**/*.yml", recursive=True))
    assets = [
        asset.replace(".yml", "")
        for asset in assets
        if not any(
            excluded in asset.replace(os.sep, "/") for excluded in EXCLUDED_ASSETS
        )
    ]

    # get list of scripts
    scripts = sorted(glob.glob("*.sh", recursive=False))
    scripts = [
        script.replace(".sh", "")
        for script in scripts
        if not any(
            excluded in script.replace(os.sep, "/") for excluded in EXCLUDED_SCRIPTS
        )
    ]

    # get list of schedules
    schedules = sorted(glob.glob("schedules/**/*schedule.yml", recursive=True))
    schedules = [
        schedule.replace(".yml", "")
        for schedule in schedules
        if not any(
            excluded in schedule.replace(os.sep, "/") for excluded in EXCLUDED_SCHEDULES
        )
    ]

    # write workflows
    write_workflows(
        jobs,
        jobs_using_registry_components,
        endpoints,
        resources,
        assets,
        scripts,
        schedules,
    )

    # read existing README.md
    with open("README.md", "r") as f:
        readme_before = f.read()

    # write README.md
    write_readme(jobs, endpoints, resources, assets, scripts, schedules)

    # read modified README.md
    with open("README.md", "r") as f:
        readme_after = f.read()

    # check if readme matches
    if args.check_readme:
        if not check_readme(readme_before, readme_after):
            print("README.md file did not match...")
            exit(2)


def modify_notebooks(notebooks):
    # setup variables
    kernelspec = {
        "display_name": "Python 3.8 - AzureML",
        "language": "python",
        "name": "python38-azureml",
    }

    # for each notebooks
    for notebook in notebooks:
        # read in notebook
        with open(notebook, "r") as f:
            data = json.load(f)

        # update metadata
        data["metadata"]["kernelspec"] = kernelspec

        # write notebook
        with open(notebook, "w") as f:
            json.dump(data, f, indent=1)


def write_readme(jobs, endpoints, resources, assets, scripts, schedules):
    # read in prefix.md and suffix.md
    with open("prefix.md", "r") as f:
        prefix = f.read()
    with open("suffix.md", "r") as f:
        suffix = f.read()

    # define markdown tables
    jobs_table = "\n**Jobs** ([jobs](jobs))\n\npath|status|description\n-|-|-\n"
    endpoints_table = (
        "\n**Endpoints** ([endpoints](endpoints))\n\npath|status|description\n-|-|-\n"
    )
    resources_table = (
        "\n**Resources** ([resources](resources))\n\npath|status|description\n-|-|-\n"
    )
    assets_table = "\n**Assets** ([assets](assets))\n\npath|status|description\n-|-|-\n"
    scripts_table = "\n**Scripts**\n\npath|status|\n-|-\n"
    schedules_table = "\n**Schedules**\n\npath|status|\n-|-\n"

    # process jobs
    for job in jobs:
        # build entries for tutorial table
        posix_job = job.replace(os.sep, "/")
        job_name = posix_job.replace("/", "-")
        status = f"[![{posix_job}](https://github.com/Azure/azureml-examples/workflows/cli-{job_name}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-{job_name}.yml)"
        description = "*no description*"
        try:
            with open(f"{job}.yml", "r") as f:
                for line in f.readlines():
                    if "description: " in str(line):
                        description = line.split(": ")[-1].strip()
                        break
        except:
            pass

        # add row to tutorial table
        row = f"[{posix_job}.yml]({posix_job}.yml)|{status}|{description}\n"
        jobs_table += row

    # process endpoints
    for endpoint in endpoints:
        # build entries for tutorial table
        posix_endpoint = endpoint.replace(os.sep, "/")
        endpoint_name = posix_endpoint.replace("/", "-")
        status = f"[![{posix_endpoint}](https://github.com/Azure/azureml-examples/workflows/cli-{endpoint_name}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-{endpoint_name}.yml)"
        description = "*no description*"
        try:
            with open(f"{endpoint}.yml", "r") as f:
                for line in f.readlines():
                    if "description: " in str(line):
                        description = line.split(": ")[-1].strip()
                        break
        except:
            pass

        # add row to tutorial table
        row = f"[{posix_endpoint}.yml]({posix_endpoint}.yml)|{status}|{description}\n"
        endpoints_table += row

    # process resources
    for resource in resources:
        # build entries for tutorial table
        posix_resource = resource.replace(os.sep, "/")
        resource_name = posix_resource.replace("/", "-")
        status = f"[![{posix_resource}](https://github.com/Azure/azureml-examples/workflows/cli-{resource_name}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-{resource_name}.yml)"
        description = "*no description*"
        try:
            with open(f"{resource}.yml", "r") as f:
                for line in f.readlines():
                    if "description: " in str(line):
                        description = line.split(": ")[-1].strip()
                        break
        except:
            pass

        # add row to tutorial table
        row = f"[{posix_resource}.yml]({posix_resource}.yml)|{status}|{description}\n"
        resources_table += row

    # process assets
    for asset in assets:
        # build entries for tutorial table
        posix_asset = asset.replace(os.sep, "/")
        asset_name = posix_asset.replace("/", "-")
        status = f"[![{posix_asset}](https://github.com/Azure/azureml-examples/workflows/cli-{asset_name}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-{asset_name}.yml)"
        description = "*no description*"
        try:
            with open(f"{asset}.yml", "r") as f:
                for line in f.readlines():
                    if "description: " in str(line):
                        description = line.split(": ")[-1].strip()
                        break
        except:
            pass

        # add row to tutorial table
        row = f"[{posix_asset}.yml]({posix_asset}.yml)|{status}|{description}\n"
        assets_table += row

    # process scripts
    for script in scripts:
        # build entries for tutorial table
        posix_script = script.replace(os.sep, "/")
        status = f"[![{posix_script}](https://github.com/Azure/azureml-examples/workflows/cli-scripts-{script}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-{script}.yml)"
        link = f"https://scripts.microsoft.com/azure/machine-learning/{script}"

        # add row to tutorial table
        row = f"[{posix_script}.sh]({posix_script}.sh)|{status}\n"
        scripts_table += row

    # process schedules
    for schedule in schedules:
        # build entries for tutorial table
        posix_schedule = schedule.replace(os.sep, "/")
        status = f"[![{posix_schedule}](https://github.com/Azure/azureml-examples/workflows/cli-schedules-{posix_schedule}/badge.svg?branch={BRANCH})](https://github.com/Azure/azureml-examples/actions/workflows/cli-schedules-{posix_schedule}.yml)"
        link = (
            f"https://schedules.microsoft.com/azure/machine-learning/{posix_schedule}"
        )

        # add row to tutorial table
        row = f"[{posix_schedule}.yml]({posix_schedule}.yml)|{status}\n"
        schedules_table += row

    # write README.md
    print("writing README.md...")
    with open("README.md", "w") as f:
        f.write(
            prefix
            + scripts_table
            + jobs_table
            + endpoints_table
            + resources_table
            + assets_table
            + schedules_table
            + suffix
        )
    print("Finished writing README.md...")


def write_workflows(
    jobs,
    jobs_using_registry_components,
    endpoints,
    resources,
    assets,
    scripts,
    schedules,
):
    print("writing .github/workflows...")

    # process jobs
    for job in jobs:
        # write workflow file
        write_job_workflow(job)

    # process jobs_using_registry_components
    for job in jobs_using_registry_components:
        # write workflow file
        write_job_using_registry_components_workflow(job)

    # process endpoints
    for endpoint in endpoints:
        # write workflow file
        write_endpoint_workflow(endpoint)

    # process assest
    for resource in resources:
        # write workflow file
        write_asset_workflow(resource)

    # process assest
    for asset in assets:
        # write workflow file
        write_asset_workflow(asset)

    # process scripts
    for script in scripts:
        # write workflow file
        write_script_workflow(script)

    # process schedules
    for schedule in schedules:
        # write workflow file
        write_schedule_workflow(schedule)


def check_readme(before, after):
    return before == after


def parse_path(path):
    filename = None
    project_dir = None
    hyphenated = None
    try:
        filename = path.split(os.sep)[-1]
    except:
        pass
    try:
        project_dir = os.sep.join(path.split(os.sep)[:-1])
    except:
        pass
    try:
        hyphenated = path.replace(os.sep, "-").replace("/", "-")
    except:
        pass

    return filename, project_dir, hyphenated


def write_job_workflow(job):
    filename, project_dir, hyphenated = parse_path(job)
    posix_project_dir = project_dir.replace(os.sep, "/")
    is_pipeline_sample = "jobs/pipelines" in job
    is_spark_sample = "jobs/spark" in job
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    # Duplicate name in working directory during checkout
    # https://github.com/actions/checkout/issues/739
    workflow_yaml = f"""{READONLY_HEADER}
name: cli-{hyphenated}
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{posix_project_dir}/**
      - infra/bootstrapping/**
      - .github/workflows/cli-{hyphenated}.yml\n"""
    if is_pipeline_sample:
        workflow_yaml += "      - cli/run-pipeline-jobs.sh\n" ""
    if is_spark_sample:
        workflow_yaml += "      - cli/jobs/spark/data/titanic.csv\n" ""
    workflow_yaml += f"""      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          echo '{GITHUB_CONCURRENCY_GROUP}';
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true\n"""
    if is_spark_sample:
        workflow_yaml += get_spark_setup_workflow(job, posix_project_dir, filename)
    workflow_yaml += f"""    - name: run job
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";\n"""
    if "automl" in job and "image" in job:
        workflow_yaml += f"""          bash \"{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh\" replace_template_values \"prepare_data.py\";
          pip install azure-identity
          bash \"{GITHUB_WORKSPACE}/sdk/python/setup.sh\"  
          python prepare_data.py --subscription $SUBSCRIPTION_ID --group $RESOURCE_GROUP_NAME --workspace $WORKSPACE_NAME\n"""
    elif "autotuning" in job:
        workflow_yaml += f"""          bash -x generate-yml.sh\n"""
        # workflow_yaml += f"""          bash -x {os.path.relpath(".", project_dir)}/run-job.sh generate-yml.yml\n"""
    workflow_yaml += f"""          bash -x {os.path.relpath(".", project_dir).replace(os.sep, "/")}/run-job.sh {filename}.yml
      working-directory: cli/{posix_project_dir}
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{posix_project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false\n"""

    # write workflow
    with open(
        f"..{os.sep}.github{os.sep}workflows{os.sep}cli-{job.replace(os.sep, '-').replace('/', '-')}.yml",
        "w",
    ) as f:
        f.write(workflow_yaml)


def write_job_using_registry_components_workflow(job):
    filename, project_dir, hyphenated = parse_path(job)
    posix_project_dir = project_dir.replace(os.sep, "/")
    folder_name = project_dir.split(os.sep)[-1]
    is_pipeline_sample = "jobs/pipelines" in job
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    # Duplicate name in working directory during checkout
    # https://github.com/actions/checkout/issues/739
    workflow_yaml = f"""{READONLY_HEADER}
name: cli-{hyphenated}-registry
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{posix_project_dir}/**
      - infra/bootstrapping/**
      - .github/workflows/cli-{hyphenated}-registry.yml\n"""
    if is_pipeline_sample:
        workflow_yaml += "      - cli/run-pipeline-jobs.sh\n" ""
    workflow_yaml += f"""      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          echo '{GITHUB_CONCURRENCY_GROUP}';
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{posix_project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: run job
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";\n"""
    if "automl" in job and "image" in job:
        workflow_yaml += f"""          bash \"{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh\" replace_template_values \"prepare_data.py\";
          pip install azure-identity
          bash \"{GITHUB_WORKSPACE}/sdk/python/setup.sh\"  
          python prepare_data.py --subscription $SUBSCRIPTION_ID --group $RESOURCE_GROUP_NAME --workspace $WORKSPACE_NAME\n"""
    workflow_yaml += f"""          bash -x {os.path.relpath(".", project_dir).replace(os.sep, "/")}/run-pipeline-job-with-registry-components.sh {filename} {folder_name}
      working-directory: cli/{posix_project_dir}\n"""

    # write workflow
    with open(
        f"..{os.sep}.github{os.sep}workflows{os.sep}cli-{job.replace(os.sep, '-').replace('/', '-')}-registry.yml",
        "w",
    ) as f:
        f.write(workflow_yaml)


def write_endpoint_workflow(endpoint):
    filename, project_dir, hyphenated = parse_path(endpoint)
    project_dir = project_dir.replace(os.sep, "/")
    deployments = sorted(
        glob.glob(project_dir + "/*deployment.yml", recursive=True)
        + glob.glob(project_dir + "/*deployment.yaml", recursive=True)
    )
    deployments = [
        deployment
        for deployment in deployments
        if not any(excluded in deployment for excluded in EXCLUDED_DEPLOYMENTS)
    ]
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    endpoint_type = (
        "online"
        if "endpoints/online/" in endpoint
        else "batch"
        if "endpoints/batch/" in endpoint
        else "unknown"
    )
    endpoint_name = hyphenated[-28:].replace("-", "") + str(
        random.randrange(1000, 9999)
    )

    create_endpoint_yaml = f"""{READONLY_HEADER}
name: cli-{hyphenated}
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{project_dir}/**
      - cli/endpoints/{endpoint_type}/**
      - infra/bootstrapping/**
      - .github/workflows/cli-{hyphenated}.yml
      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: delete endpoint if existing
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          az ml {endpoint_type}-endpoint delete -n {endpoint_name} -y
      working-directory: cli
      continue-on-error: true
    - name: create endpoint
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          cat {endpoint}.yml
          az ml {endpoint_type}-endpoint create -n {endpoint_name} -f {endpoint}.yml
      working-directory: cli\n"""

    cleanup_yaml = f"""    - name: cleanup endpoint
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          az ml {endpoint_type}-endpoint delete -n {endpoint_name} -y
      working-directory: cli\n"""

    workflow_yaml = create_endpoint_yaml

    if (deployments is not None) and (len(deployments) > 0):
        for deployment in deployments:
            deployment = deployment.replace(".yml", "").replace(".yaml", "")
            deployment_yaml = f"""    - name: create deployment
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          cat {deployment}.yml
          az ml {endpoint_type}-deployment create -e {endpoint_name} -f {deployment}.yml
      working-directory: cli\n"""

            workflow_yaml += deployment_yaml

    workflow_yaml += cleanup_yaml

    # write workflow
    with open(f"../.github/workflows/cli-{hyphenated}.yml", "w") as f:
        f.write(workflow_yaml)


def write_asset_workflow(asset):
    filename, project_dir, hyphenated = parse_path(asset)
    project_dir = project_dir.replace(os.sep, "/")
    posix_asset = asset.replace(os.sep, "/")
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    workflow_yaml = f"""{READONLY_HEADER}
name: cli-{hyphenated}
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{posix_asset}.yml
      - infra/bootstrapping/**
      - .github/workflows/cli-{hyphenated}.yml
      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: create asset
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          az ml {asset.split(os.sep)[1]} create -f {posix_asset}.yml
      working-directory: cli\n"""

    # write workflow
    with open(
        f"..{os.sep}.github{os.sep}workflows{os.sep}cli-{hyphenated}.yml", "w"
    ) as f:
        f.write(workflow_yaml)


def write_script_workflow(script):
    filename, project_dir, hyphenated = parse_path(script)
    project_dir = project_dir.replace(os.sep, "/")
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    workflow_yaml = f"""{READONLY_HEADER}
name: cli-scripts-{hyphenated}
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{script}.sh
      - infra/bootstrapping/**
      - .github/workflows/cli-scripts-{hyphenated}.yml
      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: test script script
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          set -e; bash -x {script}.sh
      working-directory: cli\n"""

    # write workflow
    with open(f"../.github/workflows/cli-scripts-{hyphenated}.yml", "w") as f:
        f.write(workflow_yaml)


def write_schedule_workflow(schedule):
    filename, project_dir, hyphenated = parse_path(schedule)
    project_dir = project_dir.replace(os.sep, "/")
    posix_schedule = schedule.replace(os.sep, "/")
    creds = CREDENTIALS
    schedule_hour, schedule_minute = get_schedule_time(filename)
    workflow_yaml = f"""{READONLY_HEADER}
name: cli-schedules-{hyphenated}
on:
  workflow_dispatch:
  schedule:
    - cron: "{schedule_minute} {schedule_hour}/{hours_between_runs} * * *"
  pull_request:
    branches:
      - main
    paths:
      - cli/{posix_schedule}.yml
      - infra/bootstrapping/**
      - .github/workflows/cli-schedules-{hyphenated}.yml
      - cli/setup.sh
concurrency:
  group: {GITHUB_CONCURRENCY_GROUP}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: check out repo
      uses: actions/checkout@v2
    - name: azure login
      uses: azure/login@v1
      with:
        creds: {creds}
    - name: bootstrap resources
      run: |
          bash bootstrap.sh
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: setup-cli
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          bash setup.sh
      working-directory: cli
      continue-on-error: true
    - name: validate readme
      run: |
          bash check-readme.sh "{GITHUB_WORKSPACE}" "{GITHUB_WORKSPACE}/cli/{project_dir}"
      working-directory: infra/bootstrapping
      continue-on-error: false
    - name: create schedule
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          az ml schedule create -f ./{posix_schedule}.yml --set name="ci_test_{filename}"
      working-directory: cli\n
    - name: disable schedule
      run: |
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/sdk_helpers.sh";
          source "{GITHUB_WORKSPACE}/infra/bootstrapping/init_environment.sh";
          az ml schedule disable --name ci_test_{filename}
      working-directory: cli\n"""

    # write workflow
    with open(f"../.github/workflows/cli-schedules-{hyphenated}.yml", "w") as f:
        f.write(workflow_yaml)


def get_schedule_time(filename):
    name_hash = int(hashlib.sha512(filename.encode()).hexdigest(), 16)
    schedule_minute = name_hash % 60
    schedule_hour = (name_hash // 60) % hours_between_runs
    return schedule_hour, schedule_minute


def get_endpoint_name(filename, hyphenated):
    # gets the endpoint name from the .yml file
    with open(filename, "r") as f:
        endpoint_name = yaml.safe_load(f)["name"]
    return endpoint_name


def get_spark_setup_workflow(job, posix_project_dir, filename):
    is_attached = "attached-spark" in job
    is_user_identity = "user-identity" in job
    is_managed_identity = "managed-identity" in job
    is_default_identity = "default-identity" in job
    workflow = f"""    - name: upload data
      run: |
          bash -x upload-data-to-blob.sh jobs/spark/
      working-directory: cli
      continue-on-error: true\n"""
    if is_managed_identity:
        workflow += f"""    - name: setup identities
      run: |
          bash -x setup-identities.sh
      working-directory: cli/{posix_project_dir}
      continue-on-error: true\n"""
    if is_attached:
        workflow += f"""    - name: setup attached spark
      working-directory: cli
      continue-on-error: true"""
    if is_attached and is_user_identity:
        workflow += f"""
      run: |
          bash -x {posix_project_dir}/setup-attached-resources.sh resources/compute/attached-spark-user-identity.yml {posix_project_dir}/{filename}.yml\n"""
    if is_attached and is_managed_identity:
        workflow += f"""
      run: |
          bash -x {posix_project_dir}/setup-attached-resources.sh resources/compute/attached-spark-system-identity.yml {posix_project_dir}/{filename}.yml\n"""
    if is_attached and is_default_identity:
        workflow += f"""
      run: |
          bash -x {posix_project_dir}/setup-attached-resources.sh resources/compute/attached-spark.yml {posix_project_dir}/{filename}.yml\n"""

    return workflow


# run functions
if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-readme", type=bool, default=False)
    args = parser.parse_args()

    # call main
    main(args)
