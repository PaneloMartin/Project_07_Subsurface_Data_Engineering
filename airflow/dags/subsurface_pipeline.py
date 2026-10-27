from datetime import datetime
import subprocess

from airflow.decorators import dag, task


PROJECT_DIR = "/opt/subsurface_project"


@dag(
    dag_id="subsurface_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["subsurface", "data-engineering"],
)
def subsurface_pipeline():

    @task
    def extract():
        print("STEP 1: Using existing LAS files")
        return "LAS files available locally"

    @task
    def transform():
        print("STEP 2: Processing real subsurface data")

        scripts = [
            "build_wells.py",
            "build_log_files.py",
            "build_curves.py",
            "build_measurements.py",
        ]

        for script in scripts:
            print(f"Running {script}", flush=True)

            subprocess.run(
                [
                    "python",
                    f"{PROJECT_DIR}/ingestion/{script}",
                ],
                check=True,
            )

        return "Four CSV files generated successfully"

    
    @task
    def load():
        print(
            "STEP 3: Loading and validating Snowflake staging",
            flush=True,
        )

        result = subprocess.run(
            [
                "python",
                "-u",
                f"{PROJECT_DIR}/ingestion/load_snowflake.py",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        print(result.stdout, flush=True)

        if result.stderr:
            print(result.stderr, flush=True)

        return "Snowflake staging load and validation completed"


    @task
    def validate():
        print("STEP 4: Snowflake staging validation completed")
        return "Validation performed by load_snowflake.py"


    extract() >> transform() >> load() >> validate()


subsurface_pipeline()