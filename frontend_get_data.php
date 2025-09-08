<?php
// Frontend script: Retrieve manual data from the AI API

$BASE_URL = getenv('API_BASE_URL') ?: 'http://127.0.0.1:5000';
$API_KEY = getenv('API_KEY') ?: 'demo-key';

// Optional type filter: category|member|profession|location|synonym|blacklist|whitelist
$type = isset($_GET['type']) ? trim($_GET['type']) : null;

$url = rtrim($BASE_URL, '/') . '/data';
if ($type) {
    $url .= '?type=' . urlencode($type);
}

$headers = [
    'X-API-Key: ' . $API_KEY,
];

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 20);

$response = curl_exec($ch);
$err = curl_error($ch);
$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

header('Content-Type: application/json');
if ($err) {
    echo json_encode(['error' => $err]);
    exit;
}

echo $response ?: json_encode(['error' => 'empty response', 'status' => $status]);

