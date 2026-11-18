**Unreleased**

* Product name Arcanna.ai; licensed under Apache 2.0.
* The Arcanna_AI_Decision and Arcanna_AI_Feedback playbooks no longer ship inside the app.
* Rebuilt on the Splunk SOAR SDK: needs Splunk SOAR 7.0 or later (Python 3.13). Actions, parameters, asset settings, output datapaths and messages are unchanged; failures are reported as "Action failure in <action>: <message>".
* export event and get platform metrics no longer list the arcanna_event, arcanna and es_cluster_metrics datapaths; the data is still returned.
