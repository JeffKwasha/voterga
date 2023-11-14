"""
handle loading the rolls into tables

Glossary:
VRID - VoterRoll ID


TODO
- create tables:
    - voters
        - Unique: VRID.date_of_roll
        - massage flags/Notes
        - peel out
            - addresses
    - vote_history / purge lists
        - simply the facts
    - addresses
        - Date start, end (construction/demolition)
        - json for address variants
        - flags
    - voter_status
        - one per VRID
        - dates
            - first registered  - READ_ONLY
            - first voted       - for comparison
            - last voted
            - last contact
            - last scanned voter roll
        - errors_found
            - first date error related voter roll
            - last date of error related voter roll
            - list of error columns
            - ...?
        - use json
        - export_to_xlsx
- import data to tables
    - Path.glob() ... tar_zst_readAll ... load_into_table
- save tables as parquet ?

-- learn SQL

"""


def do_scan(db: duckdb):
    """
    generate/update the error report table

    :param db:
    :return:
    """
    pass