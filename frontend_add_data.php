<?php
// Frontend script: Add manual data to the AI API

$BASE_URL = getenv('API_BASE_URL') ?: 'http://127.0.0.1:5000';
$API_KEY = getenv('API_KEY') ?: 'demo-key';

// Accept JSON body or form fields
$raw = file_get_contents('php://input');
$json = json_decode($raw, true);

$type = isset($_REQUEST['type']) ? trim($_REQUEST['type']) : ($json['type'] ?? 'member');
$addedBy = isset($_REQUEST['by']) ? trim($_REQUEST['by']) : ($json['added_by'] ?? 'php_admin');

// Example content; override by providing `content` in JSON body or individual query params
$content = $json['content'] ?? [
    'name' => 'Sample Member',
    'location' => 'New York, NY',
    'rating' => 4.8
];

$payload = [
    'type' => $type,
    'content' => $content,
    'added_by' => $addedBy
];

$headers = [
    'Content-Type: application/json',
    'X-API-Key: ' . $API_KEY,
];

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, rtrim($BASE_URL, '/') . '/data');
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
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

