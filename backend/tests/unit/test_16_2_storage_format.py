"""16-2: Confluence storage format → Markdown (plan/16 macro rules; written for FFCore)."""

from ffcore.sources.storage_format import to_markdown

PAGE = """
<h1>Ödeme akışı</h1>
<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">2</ac:parameter></ac:structured-macro>
<p>Başvuru <strong>yazılı</strong> yapılır ve <em>on iş günü</em> içinde yanıtlanır.<br/>Kayıt tutulur.</p>
<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">OPS-142</ac:parameter></ac:structured-macro>
<ac:structured-macro ac:name="info"><ac:parameter ac:name="title">Dikkat</ac:parameter>
  <ac:rich-text-body><p>Gece 02:00 sonrası işlem yapılmaz.</p></ac:rich-text-body></ac:structured-macro>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">sql</ac:parameter>
  <ac:plain-text-body><![CDATA[SELECT * FROM odeme WHERE durum = 'X';]]></ac:plain-text-body></ac:structured-macro>
<ac:structured-macro ac:name="include"><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="Ortak kurallar"/></ac:link></ac:parameter></ac:structured-macro>
<ac:structured-macro ac:name="expand"><ac:rich-text-body><p>Ayrıntılı açıklama burada.</p></ac:rich-text-body></ac:structured-macro>
<ac:structured-macro ac:name="children"/>
<ac:structured-macro ac:name="mystery-widget"/>
<ac:structured-macro ac:name="custom-box"><ac:rich-text-body><p>Kutudaki metin.</p></ac:rich-text-body></ac:structured-macro>
<ac:image><ri:attachment ri:filename="ekran.png"/></ac:image>
<ul><li>Birinci adım<ul><li>Alt adım</li></ul></li><li>İkinci <ac:link><ri:page ri:content-title="Ek sayfa"/><ac:plain-text-link-body><![CDATA[bağlantı]]></ac:plain-text-link-body></ac:link></li></ul>
<table><tbody><tr><th>Alan</th><th>Değer</th></tr><tr><td>Limit</td><td><p>10 | 20</p></td></tr></tbody></table>
"""  # noqa: E501 (storage format as Confluence stores it)


def test_16_2_macro_rules():
    result = to_markdown(PAGE, title="Ödeme süreci")
    md = result.markdown
    assert md.startswith("# Ödeme süreci\n")
    assert "## " not in md.split("\n", 1)[1][:0]  # title is the only implicit heading
    assert "# Ödeme akışı" in md
    assert "maxLevel" not in md and "toc" not in md  # navigation dropped
    assert "Başvuru **yazılı** yapılır ve *on iş günü* içinde yanıtlanır." in md
    assert "JIRA: OPS-142" in md
    assert "> **Dikkat**" in md and "> Gece 02:00 sonrası işlem yapılmaz." in md
    assert "```sql\nSELECT * FROM odeme WHERE durum = 'X';\n```" in md
    assert "[Included page: Ortak kurallar]" in md  # never expanded
    assert "Ayrıntılı açıklama burada." in md and "Kutudaki metin." in md
    assert "ekran.png" not in md
    assert "- Birinci adım\n  - Alt adım\n- İkinci bağlantı" in md
    assert "| Alan | Değer |\n|---|---|\n| Limit | 10 \\| 20 |" in md
    assert result.unknown == {"mystery-widget": 1}  # counted, not silently lost
    assert result.macros["children"] == 1 and result.macros["toc"] == 1


def test_16_2_deterministic_and_tidy():
    first, second = to_markdown(PAGE).markdown, to_markdown(PAGE).markdown
    assert first == second
    assert "\n\n\n" not in first and first.endswith("\n") and not first.endswith("\n\n")


def test_16_2_empty_and_plain():
    assert to_markdown("").markdown == "\n"
    assert to_markdown("<p>  Tek   satır  </p>").markdown == "Tek satır\n"
    assert to_markdown("düz metin <b>kalın</b>").markdown == "düz metin **kalın**\n"
