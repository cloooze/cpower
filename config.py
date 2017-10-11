nso_server_address = "http://10.42.241.121:8080"
nso_service_uri_create_service = "/api/running/cpower/ecm-response/create-service"
nso_service_uri_delete_service = "/api/running/cpower/ecm-response/delete-service"
nso_service_uri_modify_service = "/api/running/cpower/ecm-response/modify-service"
nso_service_timeout = 10
nso_auth_username = "admin"
nso_auth_password = "admin"


logging_level = "DEBUG"

retry_n = 3

delete_sleep_time_sec = 20
update_sleep_time_sec = 20

mgmt_vn_id = '3855c3dd-fba6-49b3-aa23-f3d7230db42c'
mgmt_vn_name = 'VN_management_VNF'

hot_package_id = 'a4246ed1-b1ea-4979-9e12-d4636e76186b'


ecm_server_address = "https://pmk03ecm.rmedlab.eld.it.eu.ericsson.se"
ecm_service_timeout = 10
ecm_service_api_orders = "/ecm_service/orders/"
ecm_service_api_vns = "/ecm_service/vns/"
ecm_service_api_ovfpackage = "/ecm_service/ovfpackages/"
ecm_service_api_hotpackage = "/ecm_service/hotpackages/"
ecm_service_api_vdcs = "/ecm_service/vdcs/"
ecm_service_api_vmvnics = "/ecm_service/vmvnics/"
ecm_service_api_services = "/ecm_service/services/"
ecm_service_api_vlinks = "/ecm_service/vlinks/"
ecm_service_api_vapps = "/ecm_service/vapps/"
ecm_service_api_vms = "/ecm_service/vms/"
ecm_service_api_delete_vrfs = "/ecm_service/vrfs/"
ecm_service_api_header_auth_key =  "cpoweradmin"
ecm_service_api_header_auth_value = "Er1css0n!"
ecm_service_api_header_tenantId_key = "TenantId"
ecm_service_api_header_tenantId_value = "Cpower-tenant"

ecm_tenant_name = "Cpower-tenant"
ecm_vdc_id = "59d1ace2-76bd-4331-b0d0-39503086038f"

# OVF packages IDs mapping
ovf_package_fortinet_1 = "378cb684-f7dc-479c-a198-afafd8a503a1"
ovf_package_fortinet_2 = ""
ovf_package_dpi_1 = "e749a0a9-d132-4ed5-90a6-fd6aaf1e4b2e"
ovf_package_dpi_2 = ""

# TO change to the following naming ovf_package_<vnf-type-name>_<create or add>
#ovf_package_fortinet_create
#ovf_package_fortinet_add
#test
#te=12
