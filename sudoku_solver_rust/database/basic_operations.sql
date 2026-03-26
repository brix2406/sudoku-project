ALTER TABLE sudokus
DELETE COLUMN "hash";

SELECT solved
FROM sudokus;