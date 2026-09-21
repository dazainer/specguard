# access_policy contract

For string role and boolean owner/locked, a locked record cannot be edited by anyone. Otherwise admins can edit regardless of ownership, editors can edit only records they own, and all other roles are denied. Return a bool. Role names are case-sensitive. Other input types are outside this contract.
