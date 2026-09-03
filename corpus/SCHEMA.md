\# Reason Code Schema



Each entry in `reason\_codes.json` must be a JSON object with these fields:



\- \*\*code\*\* (string): The reason code as issued by the network. E.g. "4855", "10.4", "13.1".

\- \*\*network\*\* (string): One of "visa", "mastercard", "rupay", "amex".

\- \*\*category\*\* (string): One of "fraud", "consumer\_dispute", "processing\_error", "authorization", "cancelled\_recurring".

\- \*\*title\*\* (string): Short human-readable name for this dispute type.

\- \*\*short\_description\*\* (string): 1-2 sentence explanation of what this reason code means.

\- \*\*required\_evidence\*\* (array of strings): snake\_case tokens for evidence types. E.g. "proof\_of\_delivery", "tracking\_number\_with\_carrier".

\- \*\*typical\_defenses\*\* (array of strings): snake\_case tokens for specific evidence items that typically win this dispute.

\- \*\*deadline\_days\*\* (integer): How many days the merchant has to respond, per the network's rules.

\- \*\*source\_citation\*\* (string): Exact section or page reference in the source document.



\## Example



{

&#x20; "code": "4855",

&#x20; "network": "mastercard",

&#x20; "category": "consumer\_dispute",

&#x20; "title": "Goods or Services Not Provided",

&#x20; "short\_description": "Cardholder claims they did not receive purchased goods or services.",

&#x20; "required\_evidence": \["proof\_of\_delivery", "tracking\_number\_with\_carrier"],

&#x20; "typical\_defenses": \["carrier\_tracking\_showing\_delivery", "signed\_pod\_for\_high\_value"],

&#x20; "deadline\_days": 45,

&#x20; "source\_citation": "Mastercard Chargeback Guide, §4.8"

}

