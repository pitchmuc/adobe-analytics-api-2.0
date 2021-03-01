# Projects in aanalytics2

This documentation will provide you with information on how to use the Project class and what can be accessed from it.\
The projects are Adobe Workspace projects that can now be retrieved by the API.

First of all the `getProjects` and `getProject` methods are BETA methods that are not supported by Adobe products.\
Therefore, they may stop working at any point in time.\
Due to that status, I will not put priority support on these features compare to other methods that are supported.

## Project class

When requesting projects with the `getProjects`, you will be able to retrieve the ProjectId from the elements returned.\
This projectId can then be used in the `getProject`method and this gives you extra information about the project content.\
The definition of the project with the different elements is returned and this is what the `Project` class will use.\
You can either call the `Project` class directly from `aanalytics2` or ask to return a class instance via the parameters.

**NOTE**: The definition are not consistent over time, therefore the `Project` class may not work on old projects.\
For that case, the solution is to open that Workspace project again and re-saved it. This will create a compatible version of the project definition.

So far we are able to realize the following calls:

```python
import aanalytics2 as api2
api2.importConfigFile('myConfig.json')

## Retrieving my company Id
login = api2.Login()
login.getCompanyId()

## I now have the company ID that I can use

myCompany = api2.Analytics('companyId')
## retrieving all projects
myProjects = myCompany.getProjects()
## Selecting only one from the dataframe returned
oneId = myProjects.loc[0]['id']

oneProject = api2.getProject(oneId)
## creating a class instance
myInstance = api2.Project(oneProject)
## returning directly an instance
myInstance = api2.getProject(oneId,projectClass=True)
```

Once you have your project class instanciated on that Project definition, you can directly see the different elements that the class have discovered.\
The instance have several attributes that you can directly see by calling the project, or playing in the jupyter notebook.

```python
myInstance
### will return
{
    "id": "5f9182b5d398fd031133662e",
    "name": "My Workspace Project Title",
    "description": "",
    "rsid": "my.rsid.used",
    "ownerName": "Surname LastName",
    "ownerId": 200225502,
    "ownerEmail": "emaili@company.com",
    "template": false,
    "curation": false,
    "version": "27",
    "nbPanels": 2,
    "nbSubPanels": 51,
    "subPanelsTypes": [
        "FreeformReportlet",
        "..."
    ],
    "nbElementsUsed": 26,
    "dimensions": [
        "variables/entrypage",
        "..."
    ],
    "metrics": [
        "metrics/pageviews",
        "..."
    ],
    "segments": [],
    "calculatedMetrics": ["calculatedmetricId"],
    "rsids": [
        "rsid"
    ]
}
```

The class as a method call `to_dict()` that will return this dictionary.

## Getting all projects details

As you can see, retrieving all of the project details with information for your company is a painful process.\
You will need to first download all of the projects ID and then loop with the `getProject` and transform them into a class.

I tried to simplify that process by creating a method that realize this process automatically for you.\
**BE CAREFUL**, that process can take a LOT of time.
Therefore there are 4 optional parameters that can definitely save you a lot of time.

`getAllProjectDetails` takes 3 optional parameters:

* projects : OPTIONAL : Takes the type of object returned from the getProjects (all data - not only the ID).
    If None is provided and you never ran the `getProjects` method, we will call the `getProjects` method and retrieve the elements.
    Otherwise you can pass either a limited list of elements that you want to check details for.
* filterNameProject : OPTIONAL : If you want to retrieve project details for project with a specific string in their name. (Non regex)
* filterNameOwner : OPTIONAL : If you want to retrieve project details for project with an owner having a specific name. (Non regex)
* useAttribute : OPTIONAL : `True` by default, it will use the projectList saved in the `listProjectIds` attribute of your instance.
    It avoids to recreates the call and can save several seconds.
    If you want to start from scratch on the retrieval process of your projects, set it to `False`.

## Find the components used

One of the most important use-cases that cannot be done directly in Adobe Analytics is where the different components are used.\
If you have a dimension or a segment, you would like to know wich projects or segment are using it.\
I have created a method that is doing that for you : `findComponentsUsage`
This method takes 7 possibles arguments.

* components : REQUIRED : list of component to look for.
    Example : evar10,event1,prop3,segmentId, calculatedMetricsId
* ProjectDetails: OPTIONAL : list of project details.
    segments : OPTIONAL : If you wish to pass the segments to look for. (should contain definition)
* calculatedMetrics : OPTIONAL : If you wish to pass the segments to look for. (should contain definition)
* recursive : OPTIONAL : if set to True, will also find the reference where the meta component are used.
    e.g. : segments based on your elements will also be searched to see where they are located..
* regexUsed : OPTIONAL : If set to True, the element are definied as a regex and some default setup is turned off.
* resetProjectDetails : OPTIONAL : Set to false by default. If set to True, it will NOT use the cache.
* verbose : OPTIONAL : print comments along the way

It will return a dictionary as a result and you can call the method like this:

```python
myElements = ['evar1','event1','prop1','segId','calcId']
findings= myCompany.findComponentsUsage(myElements)
### will be returning something like:
{
    "evar1" : {
        'segments': [
            {'segment name':'segmentsId1'},
            ...],
        'calculatedmetrics': [
            {'calculated metrics name':'calcId'},
            ...],
        'projects': [
            {'project name':'projectId'},
            ...],
    }
}
```

Some notes here about the parameters:\
**recursive**: this option is useful if you want to know a dimension (e.g. evar10) is used in a segment, but also where this segment is also used.\
This information will be provided in an additional key of the results `recursion`.\
On this key, will get a list of dictionary of element names and ids.

**regexUsed**: If you want to pass a regex in the elements searched.\
so your list could look like:`myElements = ['evar1[0-9]','event1[2-3]\d','prop1$','segId','calcId']`

### Remarks

I tried to build it in a smart way so the first run of this method will take some times but then, it will cache the result and you can realize several searched afterwards on the same results.\
There is an option to not use the cache for the projectDetails. It is the longuest process, so be careful when choosing that option.

Your elements can also be a reportSuiteId, you can also look which reportSuite id have been used.\
You can also use default dimension (e.g. : browser) and metrics (e.g. : visits)