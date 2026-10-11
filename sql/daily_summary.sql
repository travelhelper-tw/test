WITH d AS (
 SELECT prod_date,line,shift,product,COUNT(DISTINCT board_sn) bad_boards,COUNT(*) defect_count
 FROM defect_record GROUP BY prod_date,line,shift,product
)
SELECT p.*,COALESCE(d.bad_boards,0) bad_boards,COALESCE(d.defect_count,0) defect_count
FROM production_input p LEFT JOIN d USING(prod_date,line,shift,product)
ORDER BY prod_date,line,shift,product;
