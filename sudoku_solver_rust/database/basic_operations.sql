ALTER TABLE sudokus
ADD COLUMN "unsolved_hash" TEXT;

SELECT solved
FROM sudokus;