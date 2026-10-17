# Google account integration: configuration still required

APK integration currently opens Maps, Drive search, email drafts, Grab, be and Green SM. Opening an app is not OAuth authorization. No Google account tokens are acquired or stored and no email is sent automatically. Ride destination/price/booking APIs are not implemented.

To implement authenticated Drive/Gmail operations, the repository owner must first configure a Google Cloud project:

1. Create/select a project in Google Cloud Console.
2. Enable Google Drive API and Gmail API.
3. Configure Google Auth Platform branding, audience and test users. Public distribution may require Google's app verification, depending on scopes.
4. Register the Android OAuth client for package `vn.chatai.chatai_mobile`, using the actual release certificate SHA-1 from the APK build verification. Do not use a randomly generated debug certificate.
5. If server-side access is required, register a separate web OAuth client and exact HTTPS redirect URI after the backend callback is implemented. Store client secrets only in Worker secrets. Do not put a client secret in the APK or send secrets in chat.

Implementation should request the narrowest scopes required by the selected task. Prefer user-selected files for Drive; broad Drive search and Gmail reading require additional scope review. Initially use local/compose drafts and explicit send confirmation. Do not request Gmail send/modify scope merely to search mail. Never claim connected before a successful authorization response.

Before release of OAuth functionality, validate login, refresh/revocation, account switching, sign-out cleanup, user-selected file access, denied scopes and expired sessions. Keep tokens isolated by Google account and Chat AI account. Use native/browser-supported OAuth, never a password form or embedded login webview.

No Google credentials are configured by this document. The app must continue to show account access as unavailable until the actual OAuth flow is implemented and tested.
