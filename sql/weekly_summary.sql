WITH d AS (
 SELECT prod_date,line,shift,product,COUNT(DISTINCT board_sn) bad_boards,COUNT(*) defect_count
 FROM defect_record GROUP BY prod_date,line,shift,product
), g AS (
 SELECT iso_week(p.prod_date) week_key,p.line,p.shift,p.product,
 SUM(p.input_boards) input_boards,SUM(COALESCE(d.bad_boards,0)) bad_boards,
 SUM(COALESCE(d.defect_count,0)) defect_count
 FROM production_input p LEFT JOIN d USING(prod_date,line,shift,product)
 GROUP BY iso_week(p.prod_date),p.line,p.shift,p.product
), rates AS (
 SELECT *,1.0*bad_boards/input_boards bad_rate,
 1.0*SUM(bad_boards) OVER(PARTITION BY week_key)/SUM(input_boards) OVER(PARTITION BY week_key) baseline_rate
 FROM g
)
SELECT *,bad_rate/NULLIF(baseline_rate,0) rate_multiple,
 CASE WHEN input_boards>=:min_input AND bad_boards>=:min_bad THEN '樣本足夠' ELSE '樣本不足' END sample_status,
 CASE WHEN baseline_rate=0 OR bad_rate<baseline_rate*:rate_multiplier THEN '未觸發規則'
 WHEN input_boards>=:min_input AND bad_boards>=:min_bad THEN '優先調查'
 ELSE '觀察（樣本不足）' END priority
FROM rates ORDER BY week_key,line,shift,product;
