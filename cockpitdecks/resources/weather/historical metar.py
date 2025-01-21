def cleanOgi(input):
    p = map(lambda i: i.split(), input)
    output = []
    i = 0
    for l in p:
        temp = map(lambda s: s.strip("\\n"), l)
        output.append(" ".join(list(map(lambda t: t.strip("="), temp))[1:]))
        i = i + 1
    return output


def latestMetars(icao, time_window=None):
    """Gets most recent METARs in time_window number of hours before current time.

    Scrapes ogimet to get the data.

    Returns a list of python-metar objects."""
    end = datetime.datetime.utcnow()
    if time_window == None:
        time_window = 12
    start = end - datetime.timedelta(hours=time_window)
    s = start.strftime("&ano=%Y&mes=%m&day=%d&hora=%H&min=%M")
    e = end.strftime("&anof=%Y&mesf=%m&dayf=%d&horaf=%H&minf=%M")
    urlstring = "http://ogimet.com/display_metars2.php?lang=en&lugar=" + str(icao) + "&tipo=ALL&ord=REV&nil=NO&fmt=txt" + s + e + "&send=send"
    response = requests.get(urlstring)
    if response is not None:
        page = response.text.replace("\n", "")
        page = " ".join(page.split())
        rex_limited = "A string indicating ogimet has limited the response"
        limited = re.findall(rex_limited, str(page))
        # print(limited)
        if limited:
            return "ogi_limited"
        else:
            rex = "( (METAR|SPECI) .*?=)"
            metars = re.findall(rex, str(page))
            metars = [m[0] for m in metars]
            metars = cleanOgi(metars)
            metar_objects = []
            for m in metars:
                metar_objects.append(Metar.Metar(m, strict=False))
            metar_objects.reverse()
            return metar_objects
    return None
