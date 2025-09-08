# Postman Testing Guide for AI Search Suggestions API

This guide provides step-by-step instructions to test all API endpoints using Postman.

## Prerequisites

1. **Start the API Server**
   ```bash
   python app.py
   ```
   The API will be running at `http://127.0.0.1:5000`

2. **Install Postman** (if not already installed)
   - Download from: https://www.postman.com/downloads/

## Test Collection Setup

### 1. Create a New Collection
1. Open Postman
2. Click "New" → "Collection"
3. Name it "AI Search Suggestions API"
4. Add description: "Testing collection for AI Search Suggestions API"

### 2. Set Collection Variables
1. Click on your collection → "Variables" tab
2. Add these variables:
   - `base_url`: `http://127.0.0.1:5000`
   - `user_id`: `test_user_123`
   - `user_location`: `New York, NY`
   - `user_lat`: `40.7128`
   - `user_lon`: `-74.0060`

## API Endpoint Tests

### Test 1: Health Check
**Purpose**: Verify API is running and accessible

**Method**: `GET`
**URL**: `{{base_url}}/`
**Headers**: None required

**Expected Response**:
```json
{
  "status": "ok",
  "service": "bd-suggest-extended",
  "model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

**Test Script** (add in Tests tab):
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Service is running", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("ok");
});
```

---

### Test 2: Get Search Suggestions (Basic)
**Purpose**: Test basic suggestion functionality

**Method**: `POST`
**URL**: `{{base_url}}/suggest`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "current_query": "doctor near me",
  "user_id": "{{user_id}}",
  "user_search_history": ["dentist", "plumber"],
  "user_location": "{{user_location}}",
  "user_latitude": {{user_lat}},
  "user_longitude": {{user_lon}},
  "site_data": {
    "categories": [
      {
        "top_category": "Healthcare",
        "sub_category": "Medical",
        "sub_sub_category": "General Practice"
      }
    ],
    "members": [
      {
        "name": "Dr. John Smith",
        "tags": "family doctor, general practice, pediatrics",
        "location": "New York, NY",
        "reviews": "Excellent family doctor with 20 years experience",
        "rating": 4.8
      }
    ]
  }
}
```

**Expected Response**:
```json
{
  "original_query": "doctor near me",
  "suggestions": [
    "Top-rated Healthcare near you",
    "Trusted Dr. John Smith nearby",
    "Best Medical in New York",
    "Experienced General Practice near me",
    "Affordable Healthcare in New York"
  ],
  "user_id": "test_user_123",
  "timestamp": "2024-01-15T10:30:00"
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has suggestions", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.suggestions).to.be.an('array');
    pm.expect(jsonData.suggestions.length).to.be.greaterThan(0);
});

pm.test("Original query matches", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.original_query).to.eql("doctor near me");
});
```

---

### Test 3: Get Search Suggestions (Minimal Data)
**Purpose**: Test with minimal required data

**Method**: `POST`
**URL**: `{{base_url}}/suggest`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "current_query": "plumber",
  "user_id": "{{user_id}}",
  "site_data": {}
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response structure is correct", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('original_query');
    pm.expect(jsonData).to.have.property('suggestions');
    pm.expect(jsonData).to.have.property('user_id');
});
```

---

### Test 4: Submit Feedback
**Purpose**: Test feedback submission for learning

**Method**: `POST`
**URL**: `{{base_url}}/feedback`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "user_id": "{{user_id}}",
  "query": "doctor near me",
  "selected_suggestion": "Top-rated Healthcare near you",
  "success_rating": 5,
  "location": "{{user_location}}"
}
```

**Expected Response**:
```json
{
  "status": "feedback_received"
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Feedback received", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("feedback_received");
});
```

---

### Test 5: Add Manual Data (Category)
**Purpose**: Test adding manual category data

**Method**: `POST`
**URL**: `{{base_url}}/data`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "type": "category",
  "content": {
    "name": "Emergency Services",
    "description": "24/7 emergency services",
    "subcategories": ["Medical", "Fire", "Police"]
  },
  "added_by": "test_admin"
}
```

**Expected Response**:
```json
{
  "status": "data_added",
  "type": "category"
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Data added successfully", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("data_added");
    pm.expect(jsonData.type).to.eql("category");
});
```

---

### Test 6: Add Manual Data (Member)
**Purpose**: Test adding manual member data

**Method**: `POST`
**URL**: `{{base_url}}/data`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "type": "member",
  "content": {
    "name": "Dr. Jane Doe",
    "location": "Los Angeles, CA",
    "rating": 4.9,
    "specialty": "Cardiology",
    "phone": "+1-555-0123",
    "email": "jane.doe@example.com"
  },
  "added_by": "test_admin"
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Member data added", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("data_added");
    pm.expect(jsonData.type).to.eql("member");
});
```

---

### Test 7: Add Manual Data (Profession)
**Purpose**: Test adding manual profession data

**Method**: `POST`
**URL**: `{{base_url}}/data`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "type": "profession",
  "content": {
    "name": "Software Engineer",
    "description": "Full-stack development services",
    "skills": ["Python", "JavaScript", "React", "Node.js"],
    "experience_level": "Senior"
  },
  "added_by": "test_admin"
}
```

---

### Test 8: Add Manual Data (Location)
**Purpose**: Test adding manual location data

**Method**: `POST`
**URL**: `{{base_url}}/data`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "type": "location",
  "content": {
    "name": "Silicon Valley",
    "state": "California",
    "country": "USA",
    "coordinates": {
      "lat": 37.3875,
      "lon": -122.0575
    }
  },
  "added_by": "test_admin"
}
```

---

### Test 9: Get All Manual Data
**Purpose**: Retrieve all manually added data

**Method**: `GET`
**URL**: `{{base_url}}/data`
**Headers**: None required

**Expected Response**:
```json
{
  "data": [
    {
      "type": "category",
      "content": {
        "name": "Emergency Services",
        "description": "24/7 emergency services"
      }
    },
    {
      "type": "member",
      "content": {
        "name": "Dr. Jane Doe",
        "location": "Los Angeles, CA",
        "rating": 4.9
      }
    }
  ],
  "count": 2
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Data retrieved successfully", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('data');
    pm.expect(jsonData).to.have.property('count');
    pm.expect(jsonData.data).to.be.an('array');
});
```

---

### Test 10: Get Manual Data by Type
**Purpose**: Retrieve specific type of manual data

**Method**: `GET`
**URL**: `{{base_url}}/data?type=member`
**Headers**: None required

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Only member data returned", function () {
    var jsonData = pm.response.json();
    if (jsonData.data.length > 0) {
        jsonData.data.forEach(item => {
            pm.expect(item.type).to.eql("member");
        });
    }
});
```

---

### Test 11: Get Analytics
**Purpose**: Test analytics endpoint

**Method**: `GET`
**URL**: `{{base_url}}/analytics`
**Headers**: None required

**Expected Response**:
```json
{
  "statistics": {
    "total_searches": 5,
    "unique_users": 1,
    "average_rating": 5.0
  },
  "top_queries": [
    {
      "query": "doctor near me",
      "frequency": 2
    }
  ],
  "top_suggestions": [
    {
      "suggestion": "Top-rated Healthcare near you",
      "frequency": 1
    }
  ],
  "learning_patterns": {
    "doctor": 2,
    "plumber": 1
  }
}
```

**Test Script**:
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Analytics structure is correct", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('statistics');
    pm.expect(jsonData).to.have.property('top_queries');
    pm.expect(jsonData).to.have.property('top_suggestions');
    pm.expect(jsonData).to.have.property('learning_patterns');
});
```

---

## Error Testing

### Test 12: Invalid Request (Missing Query)
**Purpose**: Test error handling

**Method**: `POST`
**URL**: `{{base_url}}/suggest`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "user_id": "{{user_id}}",
  "site_data": {}
}
```

**Expected Response**:
```json
{
  "error": "current_query is required"
}
```

**Test Script**:
```javascript
pm.test("Status code is 400", function () {
    pm.response.to.have.status(400);
});

pm.test("Error message is correct", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.error).to.include("current_query is required");
});
```

---

### Test 13: Invalid Data Type
**Purpose**: Test validation for manual data

**Method**: `POST`
**URL**: `{{base_url}}/data`
**Headers**: 
- `Content-Type`: `application/json`

**Body** (raw JSON):
```json
{
  "type": "invalid_type",
  "content": {
    "name": "Test"
  }
}
```

**Expected Response**:
```json
{
  "error": "type must be one of: ['category', 'member', 'profession', 'location']"
}
```

**Test Script**:
```javascript
pm.test("Status code is 400", function () {
    pm.response.to.have.status(400);
});

pm.test("Error message mentions valid types", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.error).to.include("type must be one of");
});
```

---

## Running the Tests

### Option 1: Run Individual Tests
1. Select any request in your collection
2. Click "Send"
3. Check the response and test results

### Option 2: Run Collection
1. Click on your collection name
2. Click "Run" button
3. Select all requests or specific ones
4. Click "Run AI Search Suggestions API"
5. Review the test results

### Option 3: Run with Newman (Command Line)
```bash
# Install Newman
npm install -g newman

# Export your collection and run
newman run "AI Search Suggestions API.postman_collection.json"
```

## Test Scenarios

### Scenario 1: Complete User Journey
1. Health Check
2. Get Suggestions (with full data)
3. Submit Feedback
4. Get Analytics (to see learning)

### Scenario 2: Data Management
1. Add different types of manual data
2. Get all data
3. Get data by type
4. Get suggestions (to see manual data in results)

### Scenario 3: Error Handling
1. Test missing required fields
2. Test invalid data types
3. Test malformed JSON

## Tips for Testing

1. **Use Variables**: Set up collection variables for easy maintenance
2. **Test Scripts**: Add assertions to verify responses
3. **Environment**: Create different environments for dev/staging/prod
4. **Pre-request Scripts**: Use for dynamic data generation
5. **Collection Runner**: Use for automated testing

## Common Issues

1. **Connection Refused**: Make sure the API server is running
2. **CORS Errors**: The API includes CORS headers, but check browser console
3. **Database Errors**: Check if SQLite database is being created properly
4. **Model Loading**: First request might be slow due to model loading

## Performance Testing

For performance testing, you can:
1. Use Postman's built-in performance testing
2. Create multiple requests with different data
3. Monitor response times
4. Test with concurrent requests

This comprehensive testing guide will help you verify all functionality of your AI Search Suggestions API!
