config_object = {
    "org_id": "",
    "client_id": "",
    "tech_id": "",
    "pathToKey": "",
    "secret": "",
    "date_limit": 0,
    "token": "",
    "tokenEndpoint": "https://ims-na1.adobelogin.com/ims/exchange/jwt"
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
