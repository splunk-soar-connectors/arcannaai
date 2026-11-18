# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App

from .actions import register_actions
from .actions.platform import run_test_connectivity
from .asset import Asset


def create_app() -> App:
    app = App(
        name="Arcanna.ai",
        app_type="information",
        logo="logo_arcannaai.svg",
        logo_dark="logo_arcannaai_dark.svg",
        product_vendor="Arcanna",
        product_name="Arcanna.ai",
        publisher="Arcanna Team",
        appid="4c1f3f2e-0f6e-4d2a-9b1c-6a7d2e5b9a31",
        fips_compliant=False,
        encrypt_cache_state=True,
        encrypt_ingest_state=True,
        asset_cls=Asset,
    )

    @app.test_connectivity()
    def test_connectivity(soar: SOARClient, asset: Asset) -> None:
        """Validate the asset configuration: the v2 health endpoint must answer status OK for the API key, then the jobs are listed."""
        run_test_connectivity(soar, asset)

    return register_actions(app)


app: App = create_app()


if __name__ == "__main__":
    app.cli()
