import moto.cloudwatch.models as cloudwatch_models
import moto.cloudwatch.responses as cloudwatch_responses

from localstack import config
from localstack.services.infra import start_moto_server
from localstack.utils.common import to_unique_items_list
from localstack.utils.patch import patch


def apply_patches():
    if "<TreatMissingData>" not in cloudwatch_responses.DESCRIBE_ALARMS_TEMPLATE:
        cloudwatch_responses.DESCRIBE_ALARMS_TEMPLATE = (
            cloudwatch_responses.DESCRIBE_ALARMS_TEMPLATE.replace(
                "</AlarmName>",
                "</AlarmName><TreatMissingData>{{ alarm.treat_missing_data }}</TreatMissingData>",
            )
        )

    @patch(cloudwatch_models.CloudWatchBackend.list_metrics)
    def list_metrics(list_metrics_orig, self, *args, **kwargs):
        # Filter results to return only unique combinations of (Namespace, MetricName, Dimensions)
        # TODO: This is hugely inefficient (!), especially as the number of metric data is growing.
        #       Should be fixed upstream, or we should roll our own implementation!
        def comparator(i1, i2):
            i1 = (i1.namespace, i1.name, set((d.name, d.value) for d in i1.dimensions))
            i2 = (i2.namespace, i2.name, set((d.name, d.value) for d in i2.dimensions))
            return i1 == i2

        token, metric_list = list_metrics_orig(self, *args, **kwargs)
        metric_list = to_unique_items_list(metric_list, comparator=comparator)
        return token, metric_list

    # add put_composite_alarm

    def put_composite_alarm(self):
        return self.put_metric_alarm()

    if not hasattr(cloudwatch_responses.CloudWatchResponse, "put_composite_alarm"):
        cloudwatch_responses.CloudWatchResponse.put_composite_alarm = put_composite_alarm


def start_cloudwatch(port=None, asynchronous=False, update_listener=None):
    port = port or config.PORT_CLOUDWATCH
    apply_patches()
    return start_moto_server(
        "cloudwatch",
        port,
        name="CloudWatch",
        update_listener=update_listener,
        asynchronous=asynchronous,
    )
