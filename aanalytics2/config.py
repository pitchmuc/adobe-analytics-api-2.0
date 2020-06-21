org_id, api_key, tech_id, pathToKey, secret, companyid = "", "", "", "", "", ""
orga_admin = {'_org_admin', '_deployment_admin', '_support_admin'}
date_limit = 0
token = ''
header = {"Accept": "application/json",
          "Content-Type": "application/json",
          "Authorization": "Bearer ",
          "x-api-key": ""
          }
endpoints = {
    "global": 'https://analytics.adobe.io/api',
    "ingestion": "https://analytics-collection.adobe.io"
}
