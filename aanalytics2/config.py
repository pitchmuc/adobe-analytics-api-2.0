config_object = {
    "org_id": "",
    "client_id": "",
    "tech_id": None,
    "pathToKey": None,
    "secret": "",
    "scopes":None,
    "date_limit": 0,
    "token": "",
    "jwtTokenEndpoint": "https://ims-na1.adobelogin.com/ims/exchange/jwt",
    "oauthTokenEndpointV2" : "https://ims-na1.adobelogin.com/ims/token/v2"
}
orga_admin = {'_org_admin', '_deployment_admin', '_support_admin'}
header = {"Accept": "application/json",
          "Content-Type": "application/json",
          "Authorization": "Bearer ",
          "x-api-key": ""
          }
endpoints = {
    "global": 'https://analytics.adobe.io/api',
    "ingestion": "https://analytics-collection.adobe.io"
}
