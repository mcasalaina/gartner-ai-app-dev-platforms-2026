# Bank Servicing Agent Template package

This package publishes the existing `acmebank Blueprint` as the
`Bank Servicing Agent Template` AI teammate template. Template updates do not
rename or replace existing instances, including the `Marco's Teller` instance
used by the live bridge.

## Live bindings

- Blueprint app ID: `2c3685f3-7ad7-467b-96e8-dd3d06b99f55`
- Template: `Bank Servicing Agent Template`
- Agent instance: `Marco's Teller`
- Agent user: `marcos-teller@cam3652609.onmicrosoft.com`
- Communication protocol: `activityProtocol`
- Messaging endpoint:
  `https://marcos-teller-bridge-a365.gentleforest-8d33b38e.westus.azurecontainerapps.io/api/messages`

The manifest ID must equal the blueprint app ID. The template ID must match in
both JSON files. The four package files must be flat at the ZIP root.

Build and validate the flat package:

```bash
python scripts/publish_agent365_catalog.py \
  --manifest-dir a365/manifest
```

Agentic app packages must be published through the Microsoft 365 admin center;
the Teams app-catalog Graph upload endpoint rejects them. Open
[Agents > All agents](https://admin.cloud.microsoft/?#/agents/all), select
the existing template, choose **Update in store**, upload `manifest.zip`, and
select **Publish**.

The template package is version `2.0.2`. Its two existing instances remain
owned by `Marco Casalaina (BAMI)`; the bridge continues to use
`marcos-teller@cam3652609.onmicrosoft.com`.
