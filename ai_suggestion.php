<?php

/**
 * MySQL Query to Fetch 
 * Get the Top Categories, Sub Categories and Sub Sub Categories
 */
$query = "SELECT
    p.name AS top_category,
    GROUP_CONCAT(DISTINCT CASE WHEN s.master_id = 0 THEN s.name END SEPARATOR ', ') AS sub_categories,
    GROUP_CONCAT(DISTINCT CASE WHEN s.master_id != 0 THEN s.name END SEPARATOR ', ') AS sub_sub_categories
FROM
    list_professions AS p
LEFT JOIN
    list_services AS s ON s.profession_id = p.profession_id
GROUP BY
    p.profession_id, p.name";


/**
 * Get the Member Details 
 */
$query = "SELECT
    users_data.id,
    GROUP_CONCAT(users_data.first_name, ' ', users_data.last_name) AS name,
    users_data.email,
    users_data.phone
FROM
    users_data";

?>