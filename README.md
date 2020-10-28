
## Amazon Elastic Kubernetes Service (Amazon EKS) control plane configuration utility for CloudFormation

### What can this utility do?
You can use this utility to configure Amazon EKS control plane endpoint access and logging with CloudFormation.

Right now, it supports the following two features:

1) Configure public and private access [ Enable/Disable ]

2) Configure cluster logging levels [ Enable/Disable different cluster logging levels ]


### What is the need for this utility?
Amazon EKS control plane can be configured in many ways using tools like AWS CLI, AWS SDK, Console, etc.

However, at this time, Amazon EKS control plane endpoint access and logging is not supported out of the box by CloudFormation.
This utility fills this gap by providing a CloudFormation custom resource. 
The lambda function defined in this utility can be called by CloudFormation custom resource to configure Amazon EKS control plane.


### How does this utility work?
The lambda function uses boto3 library to configure EKS. The function can take different types of inputs and configure EKS accordingly.

If you call the function with "EndpointAccessUpdate" clusterUpdateType, the utility updates control plane access endpoints.

Similarly, you can call it with "LoggingUpdate" clusterUpdateType to update cluster logging levels.

Few thing to note about this utility:

1) While using with CloudFormation, on CREATE/UPDATE operation of CloudFormation custom resource, the lambda function updates the cluster accordingly to specified input.

2) On DELETE operation of CloudFormation custom resource, the function does not make any changes. As per your requirements, you could easily update the lambda function to handle DELETE action and set the cluster to its default state [Private endpoint - disabled , Public endpoint - enabled ; Logging - all types disabled].

3) Regarding "LoggingUpdate" operation, the tool will enable logging for all listed logging types as part of 'clusterLoggingTypes' input.
It will disable all other logging types. This behavior is little different from how AWS SDK handles the logging update. AWS SDK only updates the logging types you pass to the function call. Whereas, this tool interprets the input parameter 'clusterLoggingTypes' as list of types that should be enabled.


### How can I use it?

#### Pre-requisites
Before you can use/test this utility, you need an Amazon EKS cluster.
If you don't have one, you can follow the "Getting Started with Amazon EKS" [https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html] to quickly spin up a new EKS cluster.


#### Steps
1. Run the following command to build the package:
    ```
    sam build
    ```

2. Package and deploy the lambda function using SAM by following the below steps.

    2.1 Configure aws cli to interact with your AWS account that hosts your Amazon EKS cluster.

    2.2 Create s3 bucket and kms key to upload the code. Alternatively, you can use an existing s3 bucket and kms key.

    2.3 Run the following command to package the application, after replacing s3 and kms key placeholders
    ```
    sam package --output-template-file packaged.yaml --s3-bucket <s3-bucket-name> --s3-prefix amazon-eks-controlplane-config-util --kms-key-id <kms-key-id>
    ```

    2.4 Run the following command to deploy the function after replacing 'region' placeholder in the command:

    ```
    sam deploy --template-file packaged.yaml --stack-name amazon-eks-controlplane-config-util --capabilities CAPABILITY_NAMED_IAM --region {{region}}
    ```

    This deployment creates a function with name 'cfn-configure-eks-control-plane' and a Lambda IAM Execution role.
    You can find the logs for this lambda function in CloudWatch Logs.
    
    NOTE: The permissions of lambda execution role allows it to update any EKS cluster in your AWS account. 
    Update policy in 'ConfigureEKSControlPlaneLambdaRole' resource located in template.yaml to restrict this to required set of clusters.   
    
3. You can now configure your cluster by using 'cfn-configure-controlplane.yaml' CloudFormation template. You can customize the configuration using template parameters.  

    The template creates 2 custom resources. 
    - 'ConfigureControlPlaneLogging' resource will enable logging for all types listed in 'ClusterLoggingTypes' parameter. 
    It will disable rest of the logging types.
    
    - 'ConfigureAPIServerAccess' resource will enable/disable endpoint private and public access according to 'EndpointPublicAccess' and 'EndpointPrivateAccess' parameters.
    You can restrict the public endpoint access to specific CIDRs blocks by listing them in 'PublicAccessCidrs' parameter. 
 
Once the stack is created, you can update the cluster configuration for API endpoints or logging types by updating the existing CloudFormation stack.

NOTE: The template creates a dependency between 'ConfigureAPIServerAccess' and 'ConfigureControlPlaneLogging' resources. 
This is done to serialize the resource creation/updation, as parallel updates to these configurations are not supported at this time. 

### Limitations
The CloudFormation custom resource relies on Lambda function to update Amazon EKS cluster. 
So, the cluster updates are bound by Lambda's 15 minutes per execution limit.
In the unlikely scenario that your CloudFormation stack fails during cluster configuration update [step 3], 
check the cluster state from Amazon EKS console and update the CloudFormation stack accordingly. 


### Troubleshooting tips

Check the lambda function logs to troubleshoot any issues.
To access the logs, you can either use CLI or AWS Management Console.

- For access from console, navigate to CloudWatch -> Logs -> Log groups -> /aws/lambda/cfn-configure-eks-control-plane

- For access through CLI, you can use the following command:
    ```
    sam logs -n ConfigureEKSControlPlaneLambda --stack-name amazon-eks-controlplane-config-util --tail
    ```