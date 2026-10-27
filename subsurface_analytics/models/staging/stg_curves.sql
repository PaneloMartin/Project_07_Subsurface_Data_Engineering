{{ config(materialized='view') }}

SELECT
    FILE_ID AS file_id,
    CURVE_POSITION AS curve_position,
    MNEMONIC AS mnemonic,
    ORIGINAL_UNIT AS original_unit,
    DESCRIPTION AS curve_description,
    QUALITY_STATUS AS quality_status

FROM {{ source('raw', 'curves') }}