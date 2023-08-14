import time

import requests
from msal import PublicClientApplication


class Teams:
    def __init__(self, email: str, password: str) -> None:
        """
        Initialize a Teams object.

        :param email: User's email.
        :param password: User's password.
        """

        self.email = email
        self.password = password
        self.session = requests.Session()
        self.account_type_cache = None
        self.client_cache = None
        self.silent_token_cache = None
        self.need_login = True
        self.access_token = None
        self.refresh_token = None
        self.access_token_expiry = None

    @property
    def account_type(self) -> int | bool:
        """
        Get the account type of the user.

        :return: Account type (1 for MSAccount, 2 for OrgId), or False if unknown.
        """

        if self.account_type_cache:
            return self.account_type_cache

        account_type = self.session.get(
            f"https://odc.officeapps.live.com/odc/v2.1/idp?hm=10&emailAddress={self.email}&forcerefresh=true"
        )

        if account_type.ok:
            if account_type := account_type.json():
                if account_type := account_type.get("account", False):
                    if account_type == "MSAccount":
                        self.account_type_cache = 1
                    elif "OrgId" in account_type:
                        self.account_type_cache = 2

                    return self.account_type_cache

        return False

    @property
    def tenant_id(self) -> str | bool:
        """
        Get the tenant ID associated with the user's email domain.

        :return: Tenant ID or False if not found.
        """

        if "@" in self.email:
            domain = self.email.split("@")[-1]
            well_known_response = self.session.get(
                f"https://odc.officeapps.live.com/odc/v2.1/federationprovider?domain={domain}"
            )

            if well_known_response.ok:
                well_known_data = well_known_response.json()
                return well_known_data.get("tenantId", False)

        return False

    @property
    def authentication_metadata(self) -> dict:
        """
        Get authentication metadata based on the user's account type.

        :return: Authentication metadata dictionary.
        """

        match self.account_type:
            case 1:
                return {
                    "scope": "openid offline_access profile service::api.fl.spaces.skype.com::MBI_SSL",
                    "client_id": "8ec6bc83-69c8-4392-8f08-b3c986009232",
                    "tenant": "9188040d-6c67-4c5b-b112-36a304b66dad",
                }
            case 2:
                return {
                    "scope": "https://api.spaces.skype.com/.default",
                    "client_id": "1fec8e78-bce4-4aaf-ab1b-5451cc387264",
                    "tenant": self.tenant_id,
                }
            case _:
                return {}

    @property
    def client(self) -> bool | tuple:
        """
        Get the PublicClientApplication instance for authentication.

        :return: Tuple containing authentication metadata and PublicClientApplication instance,
                 or False if client cannot be initialized.
        """

        if self.client_cache:
            return self.client_cache

        if auth_metadata := self.authentication_metadata:
            self.client_cache = auth_metadata, PublicClientApplication(
                auth_metadata.get("client_id"),
                authority=f"https://login.microsoftonline.com/{auth_metadata.get('tenant')}",
            )

            return self.client_cache

        return False

    @property
    def is_token_expired(self) -> bool:
        """
        Check if the access token has expired.

        :return: True if the token has expired, False otherwise.
        """

        return int(time.time()) < self.access_token_expiry

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.

        :return: True if the token was successfully refreshed, False otherwise.
        """

        auth_metadata, client = self.client
        if client and self.refresh_token:
            if account := client.acquire_token_by_refresh_token(
                self.refresh_token, scopes=[auth_metadata.get("scope")]
            ):
                self.set_account_data(account)
                return True

        return False

    def set_account_data(self, account: dict) -> None:
        """
        Set account data after successful authentication.

        :param account: Account data dictionary.
        """

        self.need_login = False
        self.access_token = account.get("access_token", False)
        self.refresh_token = account.get("refresh_token", False)
        self.access_token_expiry = int(time.time()) + account.get("expires_in", 0)

    def logon_with_credentials(self) -> str | bool:
        """
        Authenticate the user using username and password.

        :return: Access token if authentication is successful, False otherwise.
        """

        auth_metadata, client = self.client
        if client:
            if account := client.acquire_token_by_username_password(
                self.email, self.password, scopes=[auth_metadata.get("scope")]
            ):
                self.set_account_data(account)
                return self.access_token

        return False

    def logon_with_devicecode(self) -> str | bool:
        """
        Authenticate the user using device code flow.

        :return: Access token if authentication is successful, False otherwise.
        """

        auth_metadata, client = self.client
        if client:
            if flow := client.initiate_device_flow(scopes=[auth_metadata.get("scope")]):
                if "message" in flow:
                    print(flow.get("message"))

                if account := client.acquire_token_by_device_flow(flow):
                    self.set_account_data(account)
                    return self.access_token

        return False

    def set_activity(self, activity: str, availability: str) -> bool:
        """
        Set user's activity and availability.

        :param activity: User's activity.
        :param availability: User's availability.
        :return: True if activity is successfully set, False otherwise.
        """

        headers = {
            "authorization": f"Bearer {self.get_access_token()}",
        }

        if self.account_type == 1:
            headers["x-ms-client-consumer-type"] = "teams4life"
            headers["x-skypetoken"] = self.x_skypetoken
            domaine = "presence.teams.live.com"

        if self.account_type == 2:
            domaine = "presence.teams.microsoft.com"

        activity_request = self.session.put(
            f"https://{domaine}/v1/me/forceavailability",
            headers=headers,
            json={
                "activity": activity,
                "availability": availability,
                "deviceType": "Mobile",
            },
        )

        if activity_request.ok:
            return True

        return False

    @property
    def silent_token(self) -> str | bool:
        """
        Get the silent token for authentication.

        :return: Silent token or False if silent token cannot be acquired.
        """

        if self.silent_token_cache:
            return self.silent_token_cache

        _, client = self.client
        accounts = client.get_accounts()
        silent_token = client.acquire_token_silent(
            scopes=[
                "openid offline_access profile service::api.fl.spaces.skype.com::MBI_SSL"
            ],
            account=accounts[0],
        )

        self.silent_token_cache = silent_token.get("access_token", False)
        return self.silent_token_cache

    @property
    def x_skypetoken(self) -> str | None:
        """
        Get the x-skypetoken for authentication.

        :return: x-skypetoken or None if it cannot be obtained.
        """

        api_url = "https://authsvc.teams.microsoft.com/v1.0/authz"
        token = self.get_access_token()
        if self.account_type == 1:
            api_url = "https://teams.live.com/api/auth/v1.0/authz/consumer"
            token = self.silent_token

        if token:
            auth_metadata, _ = self.client

            headers = {
                "authorization": f"Bearer {self.silent_token}",
                "ms-teams-authz-type": "ExplicitLogin",
                "tenantid": auth_metadata.get("tenant"),
                "user-agent": "okhttp/4.9.2",
                "username": self.email,
            }
            consumer_request = requests.post(api_url, headers=headers)

            if consumer_request.ok:
                consumer = consumer_request.json()
                if "skypeToken" in consumer and "skypetoken" in consumer.get(
                    "skypeToken"
                ):
                    return consumer.get("skypeToken").get("skypetoken")

                if "tokens" in consumer and "skypeToken" in consumer.get("tokens"):
                    return consumer.get("tokens").get("skypeToken")

        return None

    def get_access_token(self) -> str:
        """
        Get the access token for making API requests.

        :return: Access token.
        """

        if self.need_login:
            if self.account_type == 1:
                self.logon_with_devicecode()

            if self.account_type == 2:
                self.logon_with_credentials()

        if not self.is_token_expired:
            self.refresh_access_token()

        return self.access_token
