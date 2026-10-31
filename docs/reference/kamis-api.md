1	일별 부류별 도.소매가격정보
2	일별 품목별 도·소매가격정보
3	월별 도.소매가격정보 (※ 축평원 데이터는 제외됨)
4	연도별 도.소매가격정보 (※ 축평원 데이터는 제외됨)
5	친환경농산물 가격정보('05~'20.3.)
6	최근일자 도.소매가격정보(상품 기준)
7	최근 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
8	월평균 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
9	연평균 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
10	최근일자 지역별 도.소매가격정보(상품 기준)
11	친환경농산물 품목별 가격정보('05~'20.3.)
12	친환경농산물 가격정보('20.4~)
13	친환경농산물 품목별가격정보('20.4~)
14	지역별 품목별 도.소매가격정보
15	농축수산물 품목 및 등급 코드표
16	신)일별 품목별 도매 가격자료(기간설정가능, 최대1년)
17	신)일별 품목별 소매 가격자료(기간설정가능, 최대1년)
---
일별 부류별 도.소매가격정보
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_product_cls_code	string	구분 ( 01:소매, 02:도매, default:02 )
p_item_category_code	string	부류코드(100:식량작물, 200:채소류, 300:특용작물, 400:과일류, 500:축산물, 600:수산물, default:100)
p_country_code	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해)<br />* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)<br /> default : 전체지역
p_regday	string	날짜 : yyyy-mm-dd (default : 최근 조사일자)
p_convert_kg_yn	string	kg단위 환산여부(Y : 1kg 단위표시, N : 정보조사 단위표시, ex: 쌀 20kg)<br /> default : N
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList&p_product_cls_code=02&p_country_code=1101&p_regday=2015-10-01&p_convert_kg_yn=N&p_item_category_code=200&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
item_name	string	품목명
itemcode	string	품목코드
kind_name	string	품종명
kindcode	string	품종코드
rank	string	상태(상품, 중품)
unit	string	단위
day1	string	일자(조회일자)
dpr1	string	조회일자 가격
day2	string	1일전 일자(조회일자 기준)
dpr2	string	1일전 가격
day3	string	1주일전 일자(조회일자 기준)
dpr3	string	1주일전 가격
day4	string	2주일전 일자(조회일자 기준)
dpr4	string	2주일전 가격
day5	string	1개월전 일자(조회일자 기준)
dpr5	string	1개월전 가격
day6	string	1년전 일자(조회일자 기준)
dpr6	string	1년전 가격
day7	string	평년일자
dpr7	string	평년 가격
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---
일별 품목별 도·소매가격정보
안내사항
※ 해당 api는 당일로부터 1년간의 데이터만 제공하고 있습니다.
※ 1년 이상의 데이터 요청 시 관련 부서로 문의바랍니다.
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=periodProductList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_endday	string	조회기간(end date)
p_productclscode	string	구분 ( 01:소매, 02:도매, default:02 )
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countrycode	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해) &lt;br/&gt;* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)&lt;br/&gt;default : 전체지역
p_convert_kg_yn	string	kg단위 환산여부(Y : 1kg 단위표시, N : 정보조사 단위표시, ex: 쌀 20kg)&lt;br /&gt;default : N
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=periodProductList&p_productclscode=02&p_startday=2022-10-01&p_endday=2022-12-01&p_itemcategorycode=200&p_itemcode=212&p_kindcode=00&p_productrankcode=04&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
itemname	string	품목명
kindname	string	품종명
countyname	string	시군구
marketname	string	마켓명
yyyy	string	연도
regday	string	날짜
price	string	가격
샘플페이지
해당사항 없음(상위 샘플 URL 참조)
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---
월별 도.소매가격정보 (※ 축평원 데이터는 제외됨)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=monthlySalesList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_yyyy	string	연도 설정
p_period	string	기간 설정(default : 3년)
p_itemcategorycode	string	부류코드
p_kindcode	string	품종코드
p_graderank	string	등급(상품,중품)
p_countycode	string	시군구
p_convert_kg_yn	string	Kg단위 환산여부
p_itemcode	string	품목코드
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=monthlySalesList&p_yyyy=2015&p_period=3&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_graderank=2&p_countycode=1101&p_convert_kg_yn=N&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
productclscode	string	조사구분(01:소매, 02:도매)
m1 ~ m12	string	1월 ~ 12월
yyyy	string	구분(연도)
item	string	조회 결과 list
yearavg	string	연평균
caption	string	caption 정보 * 도매가격 ; 식량작물 ; 쌀 ; 일반계(중품) ; 20kg
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
200	Wrong Parameters.
900	Unauthenticated request.

---

연도별 도.소매가격정보 (※ 축평원 데이터는 제외됨)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=yearlySalesList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_kindcode	string	품종코드
p_graderank	string	등급(상품,중품) 조회
p_countycode	string	시군구코드
p_itemcode	string	품목코드
p_itemcategorycode	string	부류코드
p_yyyy	string	연도
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=yearlySalesList&p_yyyy=2015&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_graderank=1&p_countycode=1101&p_convert_kg_yn=N&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
item	string	결과리스트
div	string	구분 (연도)
avg_data	string	평균
max_data	string	최대
min_data	string	최소
stddev_data	string	표준편차
cv_data	string	변동계수
af_data	string	진폭계수
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
200	Wrong Parameters.
900	Unauthenticated request.

---

친환경농산물 가격정보('05~'20.3.)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=periodNaturePriceList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_endday	string	조회기간(end date)
regday	string	조회기간(end date)
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countrycode	string	시군구코드
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=periodNaturePriceList&p_strartday=2015-10-01&p_endday=2015-12-01&p_itemcategorycode=200&p_itemcode=212&p_kindcode=00&p_productrankcode=07&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
item	string	조회목록
seqnum	string	일련번호
countyname	string	시군구
countyname1	string	시군구
marketname	string	마켓명
unit	string	단위
regday	string	일자 yyyy-mm-dd hh:MM:SS
price	string	가격
group_first_yn	string	그룹첫번째 여부
group_last_yn	string	그룹 마지막 여부
countyname_rowspan	string	시군구 셀 병합 갯수(열)
countyname_first_yn	string	시군구 첫번째 여부
marketname_rowspan	string	마켓 셀 병합 갯수(열)
marketname_first_yn	string	마켓 첫번째 여부
샘플페이지
http://www.kamis.or.kr/customer/price/eco/period.do
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

최근일자 도.소매가격정보(상품 기준)
요청 URL (request url)
http://www.kamis.co.kr/service/price/xml.do?action=dailySalesList&p_cert_key=test&p_cert_id=test&p_returntype=xml
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=dailySalesList&p_cert_key=test&p_cert_id=test&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
product_cls_code	string	구분(01:소매, 02:도매)
product_cls_name	string	구분 이름
category_code	string	부류코드
category_name	string	부류명
productno	string	품목코드
lastest_date	string	최근조사일
productName	string	품목명
item_name	string	품목명
unit	string	단위
day1	string	최근 조사일자
dpr1	string	최근 조사일자 가격
day2	string	1일전 일자
dpr2	string	1일전 가격
day3	string	1개월전 일자
dpr3	string	1개월전 가격
day4	string	1년전 일자
dpr4	string	1년전 가격
direction	string	등락여부( 0:가격하락 1:가격상승 2:등락없음 )
value	string	등락율
result_code	string	결과코드
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
200	Wrong Parameters.
900	Unauthenticated request.

---

최근 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=dailySalesList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_regday	string	검색일자 : yyyy-mm-dd (dafuault : 최근가격조사일자)
p_cert_key	string	인증key
p_cert_id	string	요청자id
p_returntype	string	return type (json : Json data, XML: XML )
p_productno	string	품목코드(필수)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=recentlyPriceTrendList&p_productno=212&p_regday=2015-10-01&p_cert_key=test&p_cert_id=test&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
yyyy	string	연도
d40	string	40일전
d30	string	30일전
d20	string	20일전
d10	string	10일전
d0	string	당일
mx	string	최고 가격
mn	string	최저 가격
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

월평균 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=monthlyPriceTrendList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
productno	string	품목코드(필수)
p_regday	string	검색일자 (default : 최근 가격조사일자)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=monthlyPriceTrendList&p_productno=212&p_regday=2015-10-01&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
yyyymm	string	연월
max	string	최고가격
min	string	최저가격
샘플페이지
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

연평균 가격추이 조회(상품 기준) ※ 6번 API와 연동해서 사용가능 (품목코드 연계)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=yearlyPriceTrendList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
productno	string	품목코드(필수)
p_regday	string	검색일자 * default : 최근가격 조사일자
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=yearlyPriceTrendList&p_productno=212&p_regday=2015-10-01&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
yyyy	string	연도
max	string	최고가격
min	string	최저가격
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

최근일자 지역별 도.소매가격정보(상품 기준)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=dailyCountyList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_countycode	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3211:춘천, 3214:강릉, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해) <br/>* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=dailyCountyList&p_cert_key=111&p_cert_id=222&p_returntype=xml&p_countycode=1101
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
county_code	string	지역코드
county_name	string	지역명
product_cls_code	string	구분(01:소매, 02:도매)
product_cls_name	string	구분 이름
category_code	string	부류코드
category_name	string	부류명
productno	string	품목코드
lastest_date	string	최근조사일
productName	string	품목명
item_name	string	품목명
unit	string	단위
day1	string	최근 조사일자
dpr1	string	최근 조사일자 가격
day2	string	1일전 일자
dpr2	string	1일전 가격
day3	string	1개월전 일자
dpr3	string	1개월전 가격
day4	string	1년전 일자
dpr4	string	1년전 가격
direction	string	등락여부( 0:가격하락 1:가격상승 2:등락없음 )
value	string	등락율
result_code	string	결과코드
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
0	Success.
200	Wrong Parameters.
900	Unauthenticated request.

--- 

친환경농산물 품목별 가격정보('05~'20.3.)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=NaturePriceList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_regday	string	조회일자
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countrycode	string	시군구코드
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=NaturePriceList&p_regday=2019-11-28&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_productrankcode=07&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
price	string	응답 메세지
item	string	조회목록
seqnum	string	일련번호
countyname	string	시군구
countyname1	string	시군구
marketname	string	마켓명
unit	string	단위
regday	string	일자 yyyy-mm-dd hh:MM:SS
price	string	가격
group_first_yn	string	그룹첫번째 여부
group_last_yn	string	그룹 마지막 여부
countyname_rowspan	string	시군구 셀 병합 갯수(열)
countyname_first_yn	string	시군구 첫번째 여부
marketname_rowspan	string	마켓 셀 병합 갯수(열)
marketname_first_yn	string	마켓 첫번째 여부
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

친환경농산물 가격정보('20.4~)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=periodEcoPriceList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_endday	string	조회기간(end date)
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countrycode	string	시군구코드
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=periodEcoPriceList&p_strartday=2020-05-01&p_endday=2020-07-01&p_itemcategorycode=200&p_itemcode=212&p_kindcode=00&p_productrankcode=07&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
item	string	조회목록
countyname	string	시군구
marketname	string	마켓명
unit	string	단위
regday	string	일자 mm/dd
price	string	가격
샘플페이지
http://www.kamis.or.kr/customer/price/nature/period.do
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

친환경농산물 품목별가격정보('20.4~)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=EcoPriceList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_regday	string	조회일자
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countrycode	string	시군구코드
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=EcoPriceList&p_regday=2020-07-16&p_itemcategorycode=100&p_itemcode=111&p_kindcode=02&p_productrankcode=07&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
item	string	조회목록
seqnum	string	일련번호
countyname	string	시군구
marketname	string	마켓명
unit	string	단위
regday	string	일자 yyyy-mm-dd
price	string	가격
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

지역별 품목별 도.소매가격정보
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=ItemInfo
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_productclscode	string	구분 ( 01:소매, 02:도매, default:02 )
p_regday	string	조회일자
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_countycode	string	시군구 코드 <br />* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해)<br /> 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)<br /> default : 전체지역
p_convert_kg_yn	string	kg단위 환산여부
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=ItemInfo&p_productclscode=01&p_countycode=1101&p_regday=2020-07-16&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_productrankcode=07&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
item	string	조회목록
countyname	string	시군구
unit	string	단위
price	string	조회일자 가격
weekprice	string	일주일전 가격
monthprice	string	1개월전 가격
yearprice	string	1년전 가격
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
0	Success.
1	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

농축수산물 품목 및 등급 코드표
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=productInfo
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_countrycode	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해) &lt;br/&gt;* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)&lt;br/&gt;default : 전체지역
p_convert_kg_yn	string	kg단위 환산여부(Y : 1kg 단위표시, N : 정보조사 단위표시, ex: 쌀 20kg)&lt;br /&gt;default : N
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_cert_key	string	인증Key
p_endday	string	조회기간(end date)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=productInfo&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
itemcategorycode	string	부류코드
itemcategoryname	string	부류명
itemcode	string	품목코드
itemname	string	품목명
kindcode	string	품종코드
kindname	string	품종명
wholesale_unit	string	도매 출하단위
wholesale_unitsize	string	도매 출하단위 크기
retail_unit	string	소매 출하단위
retail_unitsize	string	소매 출하단위 크기
eco_unit	string	친환경 농산물출하단위(`20.4~)
eco_unitsize	string	친환경 농산물출하단위 크기(`20.4~)
whole_productrankcode	string	도매 등급
retail_productrankcode	string	소매 등급
new_natreu_productrankcode	string	친환경 등급(`20.4~)
kindname	string	품종명
price	string	가격
marketname	string	마켓명
yyyy	string	연도
regday	string	날짜
countyname	string	시군구
data	string	응답 메세지
condition	string	요청 메세지
itemname	string	품목명
샘플페이지
N/A
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.
900	Unauthenticated request.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.
000	Success.

---

신)일별 품목별 도매 가격자료(기간설정가능, 최대1년)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=periodWholesaleProductList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_endday	string	조회기간(end date)
p_countrycode	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해) &lt;br/&gt;* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)&lt;br/&gt;default : 전체지역
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_productrankcode	string	등급코드
p_convert_kg_yn	string	kg단위 환산여부(Y : 1kg 단위표시, N : 정보조사 단위표시, ex: 쌀 20kg)&lt;br /&gt;default : N
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=periodWholesaleProductList&p_startday=2024-08-01&p_endday=2024-08-09&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_productrankcode=04&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
itemname	string	품목명
kindname	string	품종명
countyname	string	시군구
marketname	string	마켓명
yyyy	string	연도
regday	string	날짜
price	string	가격
샘플페이지
해당사항 없음(상위 샘플 URL 참조)
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

---

신)일별 품목별 소매 가격자료(기간설정가능, 최대1년)
요청 URL (request url)
http://www.kamis.or.kr/service/price/xml.do?action=periodRetailProductList
요청 변수 (request parameter)
요청변수 정보 - 요청변수, 값, 설명으로 구성
요청변수	값	설명
p_countrycode	string	* 소매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2300:인천, 2401:광주, 2501:대전, 2601:울산, 3111:수원, 3214:강릉, 3211:춘천, 3311:청주, 3511:전주, 3711:포항, 3911:제주, 3113:의정부, 3613:순천, 3714:안동, 3814:창원, 3145:용인, 2701:세종, 3112:성남, 3138:고양, 3411:천안, 3818:김해) &lt;br/&gt;* 도매가격 선택가능 지역 (1101:서울, 2100:부산, 2200:대구, 2401:광주, 2501:대전)&lt;br/&gt;default : 전체지역
p_cert_key	string	인증Key
p_cert_id	string	요청자id
p_returntype	string	Return Type (json:Json 데이터 형식, xml:XML데이터형식)
p_startday	string	조회기간(start date)
p_productrankcode	string	등급코드
p_convert_kg_yn	string	kg단위 환산여부(Y : 1kg 단위표시, N : 정보조사 단위표시, ex: 쌀 20kg)&lt;br /&gt;default : N
p_itemcategorycode	string	부류코드
p_itemcode	string	품목코드
p_kindcode	string	품종코드
p_endday	string	조회기간(end date)
샘플 URL
http://www.kamis.or.kr/service/price/xml.do?action=periodRetailProductList&p_startday=2024-08-01&p_endday=2024-08-09&p_itemcategorycode=100&p_itemcode=111&p_kindcode=01&p_productrankcode=04&p_countrycode=1101&p_convert_kg_yn=Y&p_cert_key=111&p_cert_id=222&p_returntype=xml
출력 결과 필드 (response field)
출력 결과 필드 정보 - 필드, 값, 설명으로 구성
필드	값	설명
condition	string	요청 메세지
data	string	응답 메세지
itemname	string	품목명
kindname	string	품종명
countyname	string	시군구
marketname	string	마켓명
yyyy	string	연도
regday	string	날짜
price	string	가격
샘플페이지
해당사항 없음(상위 샘플 URL 참조)
비고/에러 메세지
비고/에러 메세지 정보 - code, Message로 구성
code	Message
000	Success.
001	no data
200	Wrong Parameters.
900	Unauthenticated request.

