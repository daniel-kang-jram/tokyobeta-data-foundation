function handler(event) {
    var request = event.request;
    var headers = request.headers;
    
    // Expected Authorization header value (base64-encoded "username:password")
    // This will be replaced by Terraform with actual user credentials
    var authUsers = ${auth_users_json};
    
    // Check if Authorization header is present
    var authHeader = headers.authorization;
    
    if (!authHeader) {
        return {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {
                'www-authenticate': { value: 'Basic realm="Evidence Dashboard - Enter your credentials"' }
            }
        };
    }
    
    // Extract the base64 credentials from "Basic <credentials>"
    var authValue = authHeader.value;
    
    // Validate credentials
    var isValid = false;
    for (var i = 0; i < authUsers.length; i++) {
        if (authValue === 'Basic ' + authUsers[i]) {
            isValid = true;
            break;
        }
    }
    
    if (!isValid) {
        return {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {
                'www-authenticate': { value: 'Basic realm="Evidence Dashboard - Invalid credentials"' }
            }
        };
    }
    
    // Valid credentials - allow request to proceed
    return request;
}
