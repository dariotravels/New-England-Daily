import io, re, html, datetime
import fitz
from urllib.parse import quote
import requests, feedparser, streamlit as st
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch

st.set_page_config(page_title='The New England Daily',page_icon='🗞️',layout='centered')
st.title('🗞️ The New England Daily')
st.caption('A personal newspaper connecting Nevada with New England • Generated on demand')
SECTIONS=[
 ('Front Page','major US world news headlines'),
 ('Massachusetts','Haverhill Lawrence Massachusetts local community news'),
 ('New Hampshire','Hampton New Hampshire Seacoast local news'),
 ('Maine','Portland Kennebunkport Maine local news'),
 ('Las Vegas & Henderson','Las Vegas Henderson Nevada local news'),
]
WEATHER=[('Las Vegas / Henderson, NV',36.17,-115.14,'America/Los_Angeles'),('Haverhill, MA',42.78,-71.08,'America/New_York'),('Hampton, NH',42.94,-70.84,'America/New_York'),('East Wakefield, NH',43.62,-70.98,'America/New_York'),('Portland, ME',43.66,-70.26,'America/New_York'),('Kennebunkport, ME',43.36,-70.48,'America/New_York')]
OBIT_URL='https://obituaries.eagletribune.com/'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; NewEnglandDaily/1.0)'}
def clean(s):
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(s or '')))).strip()
def fetch_news(query,n=9,days=4):
 url='https://news.google.com/rss/search?q='+quote(query+f' when:{days}d')+'&hl=en-US&gl=US&ceid=US:en'
 r=requests.get(url,headers=HEADERS,timeout=20);r.raise_for_status()
 feed=feedparser.parse(r.content)
 seen=set();result=[]
 for e in feed.entries:
  title=clean(e.get('title'))
  if not title or title.lower() in seen:continue
  seen.add(title.lower())
  source=e.get('source',{})
  result.append(dict(title=title,source=clean(source.get('title','')) if source else '',url=e.get('link',''),date=e.get('published','')))
  if len(result)>=n:break
 return result
def fetch_weather():
 results=[]
 for name,lat,lon,tz in WEATHER:
  try:
   r=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':lat,'longitude':lon,'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code','temperature_unit':'fahrenheit','timezone':tz,'forecast_days':2},timeout=18)
   r.raise_for_status();d=r.json()['daily'];results.append((name,round(d['temperature_2m_max'][0]),round(d['temperature_2m_min'][0]),d['precipitation_probability_max'][0],d['weather_code'][0]))
  except Exception:results.append((name,None,None,None,None))
 return results
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='MastCustom',fontName='Helvetica-Bold',fontSize=24,leading=29,textColor=colors.HexColor('#183653'),alignment=TA_CENTER,spaceAfter=12))
styles.add(ParagraphStyle(name='SectionCustom',fontName='Helvetica-Bold',fontSize=18,leading=23,textColor=colors.HexColor('#16607A'),spaceAfter=18))
styles.add(ParagraphStyle(name='StoryCustom',fontName='Helvetica-Bold',fontSize=12,leading=17,textColor=colors.HexColor('#1E293B'),spaceAfter=5))
styles.add(ParagraphStyle(name='MetaCustom',fontSize=9,leading=13,textColor=colors.HexColor('#526579'),spaceAfter=16))
styles.add(ParagraphStyle(name='BodyCustom',fontSize=10,leading=15,spaceAfter=12))
def p(s,style):return Paragraph(html.escape(str(s)),styles[style])
def header(canvas,doc):
 canvas.saveState();w,h=doc.pagesize
 canvas.setStrokeColor(colors.HexColor('#CAD5E0'));canvas.line(42,44,w-42,44)
 canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#526579'))
 canvas.drawString(42,31,'THE NEW ENGLAND DAILY  •  Links lead to original publishers')
 canvas.drawRightString(w-42,31,str(doc.page));canvas.restoreState()
def create_pdf(news,obits,forecast,errors):
 buf=io.BytesIO();doc=SimpleDocTemplate(buf,pagesize=(612,792),rightMargin=48,leftMargin=48,topMargin=54,bottomMargin=58)
 flow=[];date=datetime.datetime.now().strftime('%B %d, %Y')
 for idx,(section,query) in enumerate(SECTIONS):
  if idx:flow.append(PageBreak())
  flow.extend([p('THE NEW ENGLAND DAILY','MastCustom'),p(date+'  •  '+section,'SectionCustom')])
  items=news.get(section,[])
  if not items:flow.append(p('No verified headlines were retrieved for this section. Please check the original local news outlets.','BodyCustom'))
  for item in items[:8]:
   flow.append(KeepTogether([p(item['title'],'StoryCustom'),Paragraph('Source: '+html.escape(item['source'] or 'News publisher')+'  •  <link href="'+html.escape(item['url'],quote=True)+'" color="#16607A">Read original story</link>',styles['MetaCustom'])]))
 # page 6 obituaries
 flow.extend([PageBreak(),p('THE NEW ENGLAND DAILY','MastCustom'),p('Eagle-Tribune Obituaries','SectionCustom'),p('Recent obituary-related listings from the Lawrence / Haverhill area. Names and headlines below are search results, not a verified complete death-notice register.','BodyCustom')])
 for item in obits[:8]:
  flow.append(KeepTogether([p(item['title'],'StoryCustom'),Paragraph('<link href="'+html.escape(item['url'],quote=True)+'" color="#16607A">View source / verify notice</link>',styles['MetaCustom'])]))
 if not obits:flow.append(p('No recent obituary listings were retrieved. Please use the official obituary website below.','BodyCustom'))
 flow.append(Paragraph('<link href="'+OBIT_URL+'" color="#16607A">Browse The Eagle-Tribune official obituaries</link>',styles['BodyCustom']))
 # page 7 weather
 flow.extend([PageBreak(),p('THE NEW ENGLAND DAILY','MastCustom'),p('Weather: Nevada & New England','SectionCustom'),p('Today’s forecast highs and lows in °F. Weather data: Open-Meteo.','BodyCustom')])
 rows=[['Location','High','Low','Rain chance']]
 for name,hi,lo,rain,code in forecast:rows.append([name,str(hi)+'°' if hi is not None else '—',str(lo)+'°' if lo is not None else '—',str(rain)+'%' if rain is not None else '—'])
 t=Table(rows,colWidths=[260,75,75,100],repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183653')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F5F9')]),('BOTTOMPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),('FONTSIZE',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#183653'))]));flow.append(t)
 flow.extend([Spacer(1,24),p('Stories are headlines with source links, not full reproduced articles. Obituary results may be incomplete.','BodyCustom')])
 if errors:flow.append(p('Some sources were temporarily unavailable: '+', '.join(errors),'BodyCustom'))
 doc.build(flow,onFirstPage=header,onLaterPages=header);buf.seek(0);return buf.getvalue()
st.info('Press Generate Newspaper to read the latest edition right here. You can still download or print it.')
if 'edition_pdf' not in st.session_state:
 st.session_state.edition_pdf = None
 st.session_state.edition_errors = []
if st.button('🗞️ Generate Newspaper',type='primary',use_container_width=True):
 news={};errors=[]
 with st.spinner('Gathering current headlines, obituary links, and weather...'):
  for name,query in SECTIONS:
   try:news[name]=fetch_news(query)
   except Exception:news[name]=[];errors.append(name)
  try:obits=fetch_news('site:obituaries.eagletribune.com/obituary/ Eagle-Tribune',n=10,days=14)
  except Exception:obits=[];errors.append('Obituaries')
  forecast=fetch_weather()
  st.session_state.edition_pdf=create_pdf(news,obits,forecast,errors)
  st.session_state.edition_errors=errors
if st.session_state.edition_pdf:
 st.success('Your newspaper is ready! Read it below.')
 st.download_button('⬇️ Save or Print PDF',st.session_state.edition_pdf,file_name='New_England_Daily_'+datetime.date.today().isoformat()+'.pdf',mime='application/pdf',use_container_width=True)
 if st.session_state.edition_errors:
  st.warning('Some sources could not be reached: '+', '.join(st.session_state.edition_errors))
 st.markdown('### Read today’s newspaper')
 with fitz.open(stream=st.session_state.edition_pdf,filetype='pdf') as document:
  for i,page in enumerate(document):
   st.caption(f'Page {i+1} of {len(document)}')
   pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
   st.image(pix.tobytes('png'),use_container_width=True)
 st.caption('To tap article links, open the downloaded PDF. The preview pages are images for reliable viewing on iPad and iPhone.')
 st.markdown('**Obituaries:** [Read the latest directly from The Eagle-Tribune]('+OBIT_URL+')')
 st.caption('For personal use. Headlines and links are attributed to their publishers. Weather forecasts can change.')
