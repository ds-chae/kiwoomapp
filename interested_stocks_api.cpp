#include <windows.h>
#include <wininet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "wininet.lib")

#ifndef UNICODE
#define UNICODE
#endif

// Helper function to convert char* to TCHAR*
TCHAR* CharToTChar(const char* str) {
    int len = MultiByteToWideChar(CP_UTF8, 0, str, -1, NULL, 0);
    TCHAR* wstr = (TCHAR*)malloc(len * sizeof(TCHAR));
    MultiByteToWideChar(CP_UTF8, 0, str, -1, wstr, len);
    return wstr;
}

// Helper function to convert TCHAR* to char*
char* TCharToChar(const TCHAR* wstr) {
    int len = WideCharToMultiByte(CP_UTF8, 0, wstr, -1, NULL, 0, NULL, NULL);
    char* str = (char*)malloc(len);
    WideCharToMultiByte(CP_UTF8, 0, wstr, -1, str, len, NULL, NULL);
    return str;
}

// Function to send HTTPS request using WinINet
// Returns allocated buffer, caller must free it
char* SendHttpRequest(
    const char* host,
    int port,
    const char* path,
    const char* method,
    const char* data,
    const char* cookie
) {
    HINTERNET hInternet = NULL;
    HINTERNET hConnect = NULL;
    HINTERNET hRequest = NULL;
    char* response = NULL;
    DWORD responseSize = 0;
    DWORD allocatedSize = 4096;

    // Allocate response buffer
    response = (char*)malloc(allocatedSize);
    if (!response) return NULL;
    response[0] = '\0';

    // Initialize WinINet
    hInternet = InternetOpen(
        TEXT("InterestedStocksAPI/1.0"),
        INTERNET_OPEN_TYPE_DIRECT,
        NULL,
        NULL,
        0
    );

    if (!hInternet) {
        free(response);
        return NULL;
    }

    // Convert host to TCHAR
    TCHAR* wHost = CharToTChar(host);
    if (!wHost) {
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Connect to server (HTTPS)
    hConnect = InternetConnect(
        hInternet,
        wHost,
        port,
        NULL,
        NULL,
        INTERNET_SERVICE_HTTP,
        0,
        0
    );

    free(wHost);

    if (!hConnect) {
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Convert path and method to TCHAR
    TCHAR* wPath = CharToTChar(path);
    TCHAR* wMethod = CharToTChar(method);
    
    if (!wPath || !wMethod) {
        if (wPath) free(wPath);
        if (wMethod) free(wMethod);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Create HTTPS request with secure flag
    LPCWSTR acceptTypes[] = { TEXT("application/json"), NULL };
    hRequest = HttpOpenRequest(
        hConnect,
        wMethod,
        wPath,
        TEXT("HTTP/1.1"),
        NULL,
        acceptTypes,
        INTERNET_FLAG_SECURE | INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE | INTERNET_FLAG_IGNORE_CERT_CN_INVALID | INTERNET_FLAG_IGNORE_CERT_DATE_INVALID,
        0
    );

    free(wPath);
    free(wMethod);

    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Build headers
    char headers[2048] = {0};
    DWORD dataLen = data ? (DWORD)strlen(data) : 0;
    
    // Add Content-Type with UTF-8 charset
    strcpy_s(headers, sizeof(headers), "Content-Type: application/json; charset=utf-8\r\n");
    
    // Add Content-Length if there's data
    if (dataLen > 0) {
        char contentLength[64] = {0};
        sprintf_s(contentLength, sizeof(contentLength), "Content-Length: %lu\r\n", dataLen);
        strcat_s(headers, sizeof(headers), contentLength);
    }
    
    // Add Cookie if provided
    if (cookie && strlen(cookie) > 0) {
        strcat_s(headers, sizeof(headers), "Cookie: ");
        strcat_s(headers, sizeof(headers), cookie);
        strcat_s(headers, sizeof(headers), "\r\n");
    }
    
    // Headers must end with \r\n (HttpSendRequest adds the final \r\n automatically)
    // Don't add extra \r\n here

    // Convert headers to TCHAR
    TCHAR* wHeaders = CharToTChar(headers);
    if (!wHeaders) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Send request - header length should be in bytes for wide strings
    DWORD headerLen = (DWORD)wcslen(wHeaders);
    BOOL result = HttpSendRequest(
        hRequest,
        wHeaders,
        headerLen,
        dataLen > 0 ? (LPVOID)data : NULL,
        dataLen
    );

    if (wHeaders) free(wHeaders);

    if (!result) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        free(response);
        return NULL;
    }

    // Read response
    char buffer[4096];
    DWORD bytesRead = 0;
    responseSize = 0;

    while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        
        // Reallocate if needed
        if (responseSize + bytesRead + 1 > allocatedSize) {
            allocatedSize = (responseSize + bytesRead + 1) * 2;
            char* newResponse = (char*)realloc(response, allocatedSize);
            if (!newResponse) {
                free(response);
                InternetCloseHandle(hRequest);
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return NULL;
            }
            response = newResponse;
        }
        
        memcpy(response + responseSize, buffer, bytesRead);
        responseSize += bytesRead;
        response[responseSize] = '\0';
    }

    // Cleanup
    InternetCloseHandle(hRequest);
    InternetCloseHandle(hConnect);
    InternetCloseHandle(hInternet);

    return response;
}

// Add or update an interested stock
char* AddOrUpdateInterestedStock(
    const char* host,
    int port,
    const char* stockCode,
    const char* stockName,
    const char* color,
    const char* btype,
    int bamount,
    const char* cookie
) {
    // Build JSON payload
    char json[2048] = {0};
    char temp[256] = {0};
    
    sprintf_s(json, sizeof(json), "{\"stock_code\":\"%s\"", stockCode);
    
    if (stockName && strlen(stockName) > 0) {
        sprintf_s(temp, sizeof(temp), ",\"stock_name\":\"%s\"", stockName);
        strcat_s(json, sizeof(json), temp);
    } else {
        strcat_s(json, sizeof(json), ",\"stock_name\":null");
    }
    
    if (color && strlen(color) > 0) {
        sprintf_s(temp, sizeof(temp), ",\"color\":\"%s\"", color);
        strcat_s(json, sizeof(json), temp);
    } else {
        strcat_s(json, sizeof(json), ",\"color\":null");
    }
    
    if (btype && strlen(btype) > 0) {
        sprintf_s(temp, sizeof(temp), ",\"btype\":\"%s\"", btype);
        strcat_s(json, sizeof(json), temp);
    } else {
        strcat_s(json, sizeof(json), ",\"btype\":null");
    }
    
    if (bamount > 0) {
        sprintf_s(temp, sizeof(temp), ",\"bamount\":%d", bamount);
        strcat_s(json, sizeof(json), temp);
    } else {
        strcat_s(json, sizeof(json), ",\"bamount\":null");
    }
    
    strcat_s(json, sizeof(json), "}");

    char path[] = "/api/interested-stocks";
    char* response = SendHttpRequest(host, port, path, "POST", json, cookie);
    
    return response;
}

// Delete an interested stock
char* DeleteInterestedStock(
    const char* host,
    int port,
    const char* stockCode,
    const char* cookie
) {
    char path[256] = {0};
    sprintf_s(path, sizeof(path), "/api/interested-stocks/%s", stockCode);
    char* response = SendHttpRequest(host, port, path, "DELETE", "", cookie);
    
    return response;
}

// Get all interested stocks
char* GetInterestedStocks(
    const char* host,
    int port,
    const char* cookie
) {
    char path[] = "/api/interested-stocks";
    char* response = SendHttpRequest(host, port, path, "GET", "", cookie);
    
    return response;
}

// Example usage
int main() {
    // Configuration
    char host[] = "localhost";  // Change to your server host
    int port = 443;              // HTTPS default port (change if using custom port)
    char cookie[] = "token=your_auth_token_here";  // Replace with actual auth token

    wprintf(TEXT("=== Interested Stocks API Example ===\n\n"));

    // Example 1: Add/Update an interested stock
    wprintf(TEXT("1. Adding/Updating interested stock...\n"));
    char* response1 = AddOrUpdateInterestedStock(
        host, port,
        "005930",           // Stock code (Samsung Electronics)
        "삼성전자",          // Stock name
        "R",                // Color (빨)
        "CL",               // BType
        100,                // BAmount
        cookie
    );
    if (response1) {
        printf("Response: %s\n\n", response1);
        free(response1);
    }

    // Example 2: Update with different values
    wprintf(TEXT("2. Updating stock with different values...\n"));
    char* response2 = AddOrUpdateInterestedStock(
        host, port,
        "005930",
        "삼성전자",
        "G",                // Changed color to 초 (Green)
        "PCL",              // Changed BType to PCL
        200,                // Changed BAmount to 200
        cookie
    );
    if (response2) {
        printf("Response: %s\n\n", response2);
        free(response2);
    }

    // Example 3: Add another stock
    wprintf(TEXT("3. Adding another stock...\n"));
    char* response3 = AddOrUpdateInterestedStock(
        host, port,
        "000660",           // Stock code (SK Hynix)
        "SK하이닉스",
        "B",                // Color (파 - Blue)
        "HCL",              // BType
        150,
        cookie
    );
    if (response3) {
        printf("Response: %s\n\n", response3);
        free(response3);
    }

    // Example 4: Get all interested stocks
    wprintf(TEXT("4. Getting all interested stocks...\n"));
    char* response4 = GetInterestedStocks(host, port, cookie);
    if (response4) {
        printf("Response: %s\n\n", response4);
        free(response4);
    }

    // Example 5: Delete an interested stock
    wprintf(TEXT("5. Deleting interested stock...\n"));
    char* response5 = DeleteInterestedStock(host, port, "000660", cookie);
    if (response5) {
        printf("Response: %s\n\n", response5);
        free(response5);
    }

    return 0;
}
