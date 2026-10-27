-- Every measurement must match a curve
-- using the composite key (file_id, mnemonic).

SELECT
    m.file_id,
    m.depth,
    m.mnemonic
FROM {{ ref('stg_measurements') }} AS m
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ ref('stg_curves') }} AS c
    WHERE c.file_id = m.file_id
      AND c.mnemonic = m.mnemonic
)