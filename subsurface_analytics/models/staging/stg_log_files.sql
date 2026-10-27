{{ config(materialized='view') }}

SELECT
    FILE_ID AS file_id,
    KGS_ID AS well_id,
    CATALOG_URL AS catalog_url,
    DOWNLOAD_URL AS download_url,
    DEPTH_START AS depth_start,
    DEPTH_STOP AS depth_stop,
    FILE_SIZE_BYTES AS file_size_bytes

FROM {{ source('raw', 'log_files') }}