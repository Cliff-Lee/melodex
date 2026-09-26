# Installing third-party providers

Desktop Melodex can install `.mdxprovider` packages.

1. Open **Sources**.
2. Choose **Install `.mdxprovider`**.
3. Select the provider package.
4. Review the provider identity and requested permissions.
5. Install.

Providers run outside the Melodex GUI process and communicate through MPP v1 JSON-RPC.

Do not install providers you do not trust. A provider with network permission can communicate with the hosts declared in its manifest, and third-party provider code has the normal permissions of your user account unless additionally sandboxed by the operating system.
