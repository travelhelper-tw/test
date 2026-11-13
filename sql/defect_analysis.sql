SELECT iso_week(d.prod_date) week_key,d.line,d.shift,d.product,d.defect_code,
 c.defect_name,c.defect_category,COUNT(*) defect_count
FROM defect_record d JOIN defect_code c USING(defect_code)
GROUP BY iso_week(d.prod_date),d.line,d.shift,d.product,d.defect_code
ORDER BY week_key,line,shift,product,defect_count DESC,d.defect_code;
