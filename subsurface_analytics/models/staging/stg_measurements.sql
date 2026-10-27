{{ config(materialized='view') }}

SELECT
    FILE_ID AS file_id,
    DEPTH AS depth,
    MNEMONIC AS mnemonic,
    VALUE AS measurement_value

FROM {{ source('raw', 'measurements') }}