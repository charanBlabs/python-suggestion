<?php
// Frontend script: Request suggestions from the AI API

$BASE_URL = getenv('API_BASE_URL') ?: 'http://127.0.0.1:5000';
$API_KEY = getenv('API_KEY') ?: 'demo-key';
$AB_VARIANT = isset($_GET['ab']) ? $_GET['ab'] : null; // optional A/B variant

// Input parameters (GET or POST)
$query = isset($_REQUEST['q']) ? trim($_REQUEST['q']) : 'plumber near me';
$userId = isset($_REQUEST['uid']) ? trim($_REQUEST['uid']) : 'php_user_123';
$userLocation = isset($_REQUEST['loc']) ? trim($_REQUEST['loc']) : 'New York, NY';
$userLat = isset($_REQUEST['lat']) ? floatval($_REQUEST['lat']) : 40.7128;
$userLon = isset($_REQUEST['lon']) ? floatval($_REQUEST['lon']) : -74.0060;
$debug = isset($_REQUEST['debug']) ? filter_var($_REQUEST['debug'], FILTER_VALIDATE_BOOLEAN) : false;

$payload = [
    'current_query' => $query,
    'user_id' => $userId,
    'user_search_history' => ['plumber', 'dentist'],
    'user_location' => $userLocation,
    'user_latitude' => $userLat,
    'user_longitude' => $userLon,
    'debug' => $debug,
    'site_data' => [
        'settings' => [ 'radius_km' => 50 ],
        'members' => [
            [
                'id' => 1,
                'name' => "Mike's Plumbing",
                'tags' => 'plumber, drain cleaning',
                'location' => 'New York, NY',
                'rating' => 4.7,
                'latitude' => 40.713,
                'longitude' => -74.005,
                'profile_url' => 'https://example.com/m/1'
            ]
        ]
    ]
];

$headers = [
    'Content-Type: application/json',
    'X-API-Key: ' . $API_KEY,
];
if ($AB_VARIANT) {
    $headers[] = 'X-AB-Variant: ' . $AB_VARIANT;
}

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, rtrim($BASE_URL, '/') . '/suggest');
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

