import docx2txt
import re
import pandas as pd
from docx import Document
import streamlit as st

# REGEX patterns
speaker_pattern = re.compile(r"[A-ZÄÖÜ .]+:")
num_pattern = re.compile(r"\d+\/\d+")
timestamp_pattern = re.compile(r"\d+:\d+:\d+:\d+")
time_duration_pattern = re.compile(
    r"(?:\d+:\d+:\d+:\d+\s+-\s+\d+:\d+:\d+:\d+)|(?:\d+:\d+:\d+:\d+\s+-\s+\(null\))"
)


def replace_umlauts(text) -> str:
    """replace special German umlauts (vowel mutations) from text.
    ä -> ae, Ä -> Ae...
    ü -> ue, Ü -> Ue...
    ö -> oe, Ö -> Oe...
    ß -> ss
    """
    vowel_char_map = {
        ord("ä"): "ae",
        ord("ü"): "ue",
        ord("ö"): "oe",
        ord("ß"): "ss",
        ord("Ä"): "AE",
        ord("Ü"): "UE",
        ord("Ö"): "OE",
    }
    return text.translate(vowel_char_map)


def parse_docx(path, use_streamlit=False) -> tuple[str, list[dict]]:
    """
    Wrapper function for parsing a DOCX file.
    Args:
        path (str): The path to the DOCX file.
        use_streamlit (bool): Whether to use Streamlit for progress bar.
    Returns:
        tuple: A tuple containing the status message and the extracted data.
    """
    text = docx2txt.process(path)

    document = Document(path)

    tables = document.tables
    for i in tables[0].rows[0].cells:
        stripped = i.text.replace("\n", "").replace("\xa0", "").replace(" ", "")
        if stripped != "":
            first_table_text = i.text
            break

    success = True
    try:
        start_line = text.index(first_table_text) - 1
        body_text = text[start_line:]
    except:
        success = False
    if re.search(r"\d+:\d+:\d+:\d+", body_text) is None:
        return "Error: No timestamps found", None
    if re.search(r"\d+:\d+:\d+:\d+\s+-\s+\d+:\d+:\d+:\d+", body_text):
        status, res = parse_takebar_format(body_text, use_streamlit)
    else:
        status, res = parse_tabular_format(body_text, use_streamlit)

    if status != "OK":
        return status, None
    if not success:
        return "Error: No timestamps found", None
    return status, res


def parse_tabular_format(my_text, use_streamlit: bool = True) -> tuple[str, list[dict]]:
    """
    Parses a DOCX file containing a tabular script (see samples 02 and 03).
    Returns:
        tuple: A tuple containing the status message and the extracted data.
    """

    if use_streamlit:
        my_bar = st.progress(0, text="Processing...")

    data = []
    timestamps = re.findall(timestamp_pattern, my_text)
    match = re.split(timestamp_pattern, my_text)

    i = 0
    for m in match:
        # Capitalized alphanumeric string followed by a colon
        line = [j for j in m.splitlines() if j not in ["\xa0", "", "\xa0 "]]

        if not line or line[0].startswith("Take "):
            continue
        if i >= len(timestamps):
            break

        start, end = timestamps[i], timestamps[i + 1]
        i += 2

        while True:
            if line == []:
                break
            old_line = line
            if speaker_pattern.match(line[0]):
                speaker = line[0][:-1]
            elif num_pattern.match(line[0]):
                res = {
                    "speaker": "",
                    "dialogue": "",
                    "take_num": line[0],
                    "start": start,
                    "end": end,
                }
                data.append(res)
                break
            else:
                break
            dialogue = line[1]
            next = 2
            if next >= len(line):
                res = {
                    "speaker": speaker,
                    "dialogue": dialogue,
                    "take_num": take_num,
                    "start": start,
                    "end": end,
                }
                data.append(res)
                break
            if not re.match(speaker_pattern, line[2]) and not re.match(
                num_pattern, line[2]
            ):
                dialogue += line[2]
                next = 3
            if next >= len(line):
                break
            if re.match(num_pattern, line[next]):
                take_num = line[next]
                line = line[next + 1 :]
            elif re.match(speaker_pattern, line[next]):
                # print("Multiple takes")
                line = line[next:]

            res = {
                "speaker": speaker,
                "dialogue": dialogue,
                "take_num": take_num,
                "start": start,
                "end": end,
            }
            data.append(res)
            if line == old_line:
                print("Something went wrong")
                break

        if use_streamlit:
            my_bar.progress(int(i / len(timestamps) * 100))

    return "OK", data


def parse_takebar_format(
    my_text, use_streamlit: bool = True
) -> tuple[str, list[dict]]:
    """
    Parses a DOCX file containing a takebar script (see sample 01).
    Returns:
        tuple: A tuple containing the status message and the extracted data.
    """
    if use_streamlit:
        my_bar = st.progress(0, text="Processing...")

    timestamps = []
    for i in re.findall(time_duration_pattern, my_text):
        a, b = i.split(" - ")
        timestamps.append(a)
        timestamps.append(b)

    match = re.split(time_duration_pattern, my_text.replace("`", ""))
    data = []
    i = 0
    for m in match:
        if use_streamlit:
            my_bar.progress(int(i / len(timestamps) * 100))
        line = [j for j in m.splitlines() if j not in ["\xa0", "", "\xa0 "]]
        if not line or line[0].startswith("Take ") or line == [" - "]:
            continue
        if i >= len(timestamps):
            break
        t0, t1 = timestamps[i], timestamps[i + 1]
        i += 2
        in_kopierer = False
        in_atake = False
        try:
            take_num = line[0].replace(" ", "").replace("‹", "")
            line = line[1:]
            while True:
                if line == []:
                    break
                if line[0] == "\t":
                    line = line[1:]
                    continue
                if line[0] == "\t":
                    line = line[1:]
                    continue
                if line[0].find("\t") != -1:
                    a = line[0].split("\t")
                else:
                    speaker = line[0]
                    dialogue = ""
                    line = line[1:]
                    data.append(
                        {
                            "speaker": speaker,
                            "dialogue": dialogue,
                            "take_num": take_num,
                            "start": timestamps[i],
                            "end": timestamps[i + 1],
                        }
                    )
                    continue
                if in_kopierer and a[0] == "":
                    a = a[1:]
                else:
                    in_kopierer = False
                if in_atake and a[0] == "":
                    a = a[1:]
                    note = "A"
                    take_num = take_num + note
                else:
                    in_atake = False

                if a[0] == "":
                    dialogue = a[1]
                else:
                    if a[0] == "A-TAKE":
                        try:
                            speaker = a[1]
                            dialogue = a[2]
                        except:
                            speaker = ""
                            dialogue = a[1]
                        note = "A"
                        take_num = take_num + note
                        in_atake = True
                    elif a[0] == "KOPIERER":
                        speaker = a[1]
                        dialogue = a[2]
                        in_kopierer = True
                    else:
                        speaker = a[0]
                        if len(a) > 1:
                            dialogue = a[1]
                        else:
                            dialogue = ""
                data.append(
                    {
                        "speaker": speaker,
                        "dialogue": dialogue,
                        "take_num": take_num,
                        "start": t0,
                        "end": t1,
                    }
                )
                line = line[1:]
        except:
            print("Something went wrong")
            data.append(
                {
                    "speaker": "",
                    "dialogue": "ERROR",
                    "take_num": take_num,
                    "start": t0,
                    "end": t1,
                }
            )
    return "OK", data


def adapt_data(data) -> pd.DataFrame:
    """
    Adapts the data to a DataFrame, renames columns and converts types.
    """

    df = pd.DataFrame(data)
    df["Typ"] = ""

    for i, row in df.iterrows():
        if row["take_num"][-1] in ["A", "a", "Ü", "ü"]:
            df.at[i, "Typ"] = replace_umlauts(row["take_num"][-1])
            df.at[i, "take_num"] = row["take_num"][:-1]
        if df.at[i, "take_num"].find("/") != -1:
            df.at[i, "take_num"] = int(df.at[i, "take_num"].split("/")[1])
        df.at[i, "speaker"] = replace_umlauts(row["speaker"]).upper()
        df.at[i, "dialogue"] = replace_umlauts(row["dialogue"])

    df.columns = ["Rolle", "Text", "TakeNr", "In", "Out", "Typ"]
    df = df[["TakeNr", "In", "Out", "Typ", "Rolle", "Text"]]
    return df
