PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS defect_code (
 defect_code TEXT PRIMARY KEY, defect_name TEXT NOT NULL, defect_category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_batch (
 batch_id TEXT PRIMARY KEY, report_date TEXT NOT NULL, revision_no INTEGER NOT NULL CHECK(revision_no>0),
 sha256 TEXT NOT NULL, source_file TEXT NOT NULL, archive_path TEXT NOT NULL,
 imported_at TEXT NOT NULL, reason TEXT NOT NULL,
 input_rows INTEGER NOT NULL, input_boards INTEGER NOT NULL, bad_boards INTEGER NOT NULL,
 defect_rows INTEGER NOT NULL, UNIQUE(report_date, revision_no)
);
CREATE TABLE IF NOT EXISTS production_input (
 prod_date TEXT NOT NULL, line TEXT NOT NULL, shift TEXT NOT NULL CHECK(shift IN ('早','晚')),
 product TEXT NOT NULL, input_boards INTEGER NOT NULL CHECK(input_boards>0),
 batch_id TEXT NOT NULL REFERENCES import_batch(batch_id) DEFERRABLE INITIALLY DEFERRED,
 source_sheet TEXT NOT NULL, source_row INTEGER NOT NULL,
 PRIMARY KEY(prod_date,line,shift,product)
);
CREATE TABLE IF NOT EXISTS defect_record (
 defect_id TEXT PRIMARY KEY, prod_date TEXT NOT NULL, line TEXT NOT NULL,
 shift TEXT NOT NULL, product TEXT NOT NULL, board_sn TEXT NOT NULL,
 defect_code TEXT NOT NULL REFERENCES defect_code(defect_code),
 position TEXT NOT NULL, inspection_station TEXT NOT NULL,
 batch_id TEXT NOT NULL REFERENCES import_batch(batch_id) DEFERRABLE INITIALLY DEFERRED,
 source_sheet TEXT NOT NULL, source_row INTEGER NOT NULL,
 FOREIGN KEY(prod_date,line,shift,product) REFERENCES production_input(prod_date,line,shift,product)
);
CREATE TABLE IF NOT EXISTS active_daily_report (
 report_date TEXT PRIMARY KEY,
 batch_id TEXT NOT NULL REFERENCES import_batch(batch_id)
);
