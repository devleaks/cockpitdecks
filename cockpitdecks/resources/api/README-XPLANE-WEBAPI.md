# X-Plane Web API

Added integration with new [X-Plane Web API](https://developer.x-plane.com/article/x-plane-web-api/)
(X-Plane release 12.1.4+).

This addition follows the experimental spirit of this development.
I works but could certainly benefit from more robust implementation.
For exemple, there is no attempt to automatically reconnect if connection fails, etc.
However, it works and can be used to set the base for a more reliable development.

THe main advantage of the development is that, thanks to the new Web API,
g3 no longer relies on a intermediate server to present the data.
The browser directly fetches the data from the simulator software,
convert it to a form suitable for g3.
It behaves like a proxy for X-Plane Datarefs.

Currently, X-Plane (r. 12.1.4) only submit value updates when the value is first requested
and when the value has changed.
It does not send value if the value does not change in the simulation software.


# Integration

## Metrics - Dataref Mapping

*Before* using panel(), create a JavaScript global variable with the mapping
between g3 metrics and X-Plane datarefs: Unit is the unit of the dataref value,
not the metric.

```js
const METRICS = [
    {
        "metric": "pitch",
        "dref": "sim/cockpit2/gauges/indicators/pitch_vacuum_deg_pilot",
        "unit": "deg"
    },
    {
        "metric": "heading",
        "dref": "sim/cockpit2/gauges/indicators/heading_vacuum_deg_mag_pilot",
        "unit": "deg"
    },
    ...
];


var p = panel(...);
```

Each metric entry preserves the presentation (is the same as) in the demonstration panels.


## WebSocket Declaration

In panel, use a _WebSocket URL_ (starts with `ws:`) to connect to X-Plane. Example:

```js
g3.panel()
    .interval(0).url("ws://127.0.0.1:8086/api/v2")
    .append(... )
```

Panel code has been adjusted to capture the WebSocket URL and behave accordingly.


### Adjustment Notes

Adjustments include the following: In case of the use of a WebSocket:

1. Creation of WebSocket, and installation (see below).
2. Collect each dataref necessary for metrics in use (from `controller.indicators()` list).
3. For these datarefs, fetch their ids since they are requested by X-Plane Web API to refer to them.
This is done through a single call to the REST API.
4. Request X-Plane to send value updates for these Datarefs.

That's it.

Installation of the WebSocket has `.on()` callback set to
1. present Dataref values into corresponding metrics value, and
2. send metrics values to gauges through the `controller()` call.

Nothing more. Nothing less.

In the source code, a single addition to the if/then/else selection of gauge metric source
adds the necessary code to handle WebSocket interaction.
Everything is contained there,
at the expense of adding a global variable called `METRICS` to provide the mapping of metrics to Datarefs.


```js
    if (!url) {
      // fake metrics
      ...
    } else if (interval) {
      // with non-zero interval, poll an endpoint
      ...
    // CODE ADDED STARTS HERE
    } else if (url.protocol == "ws:") {
      // WebSocket Handling code
      let ws = new WebSocket(url.href);
      ...

    // CODE ADDED ENDS HERE
    } else {
      // set interval to 0 or None to use server-sent event endpoint
      let source = new EventSource(url);
      ...
    }
```


## Simplifications

If something fails, it is ignored with a message on JavaScript console.

Example of failures are:
- Metric does not supply a Dataref,
- Non existant dataref,
- Dataref is not a numeric value,

If a gauge requests more than one value, it is the gauge's responsibility
to handle the supplied array of (numeric) values.


## Enhancements

It possible to extend the code to:
- Base metrics on more than one dataref
- Change (adjust) the value of the dataref(s) before using it as a metric

Here is a suggested pattern for metrics declaration. A Formula is an expression
that combines several datarefs into a single numeric value

```
{
    metric: Total fuel,
    formula: ${leftTank} + ${rightTank},
    unit: liter
}
```


## Testing

Tested with tutorial gauge (using engine RPM as a metric).

Tested with demonstration panel (most gauge working with Cessna C172).
No need of an intermediate (proxy) web server,
g3 directly accesses X-Plane through its new Web API.


Enjoy

Last updated: 03-APR-2025