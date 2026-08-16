10 rem save"lunalight",8,1
20 clr:printchr$(8)
22 rem hot variables first: basic scans the variable table linearly
24 m2=.:po=.:pz=.:pp=.:hm=.:p=.:q=.:fr=.:jd=.:jv=.:z$="":hz=.:e2=.:tk=.:dt=.:lt=.
26 w0=53248:w1=53249:w2=53250:w3=53251:w7=53269:w8=53264:w9=53279:nq=2041:sf=54276
27 fm=.:fh=227:fx=.:fy=.:rz=1:rem x-msb writes carry the flag: bit 4 is sprite 4, 227 is 243 less that bit

28 ka=.03:gv=.:th=.:t6=.:fe=.:am=.:ae=.:ah=.:av=.:af=.:ap=.:aa=.:ag=.:tx=.:al=.:cd=.:cc=.:cr=.:cv=.:ch=.:cn=.:xz=.:q$="":rb=18432:ri=.
29 rv$="lunalight":bp=.:js=56320:bl$="                                        ":rem spc() only moves the cursor; blanking needs real spaces
30 dimpx(5),pw(5),py(5),pb(5),rf(5),ph(5),h(39)
35 gosub1800:sys16896:gosub1850:gosub1020:gosub990
40 print"{clr}":v=53248:js=56320:sn=1504:s=54272:bc=54272:c$="{left} ":poke53280,11:poke53281,0
50 t1$="{rvon}vel {rvof}":t2$="{rvon}fuel{rvof}":t3$="{rvon}horz{rvof}":ep=250:hp=-8
55 om2=-999:ofe=-999:ohm=-999:o1=-1:o2=-1:o3=-1
60 pn=2040:fe=1000:fu=fe:nm=4:nf=.:n2=ni:gosub1100
70 pokev+41,1:pokev+42,6:poke2042,253:poke2043,254
80 pokev+4,60:pokev+5,60:pokev+6,60:pokev+7,60
90 po=28:pz=28:pp=ep:hm=hp:ep=ep-23:ifep=20thenep=250
95 ifam=.then100
96 iffe<450thenpt=.:goto60
97 gosub1920
100 hp=hp+2:ifhp>8thenhp=-8
110 e2=.:hz=.:x=peek(v+31):pokev+39,0:pokev+40,0:pokew8,fm
112 ifam=.then120
114 wx=tx-56:ifwx<32thenwx=tx+56
116 pp=wx:ifwx>255thene2=1:pp=wx-256:pokew8,fh
120 ifn2>nc thenn2=nb
130 p=187:m2=n2*10:n2=n2+ns:pokev+17,peek(v+17)or16
135 lt=ti:pokev+21,29:pokev+39,12:pokev+40,8:gosub1500:gosub1600:o1=-1:o2=-1:o3=-1:rem print recoloured the labels
160 dt=ti-lt:ifdt<.thendt=1
165 ifdt>3thendt=3
170 lt=ti
172 fortk=1todt:gosub200:ifhzthen639
176 next:goto500
200 getz$:jv=peek(js):ifam=.then205
202 ifz$<>""then20
204 if(jvand31)<>31then20
205 fr=jvand16:jd=15-(jvand15)
206 ifz$=""then210
207 ifz$="{rght}"thenjd=8
208 ifz$="{down}"thenjd=4
209 ifz$="{f1}"thenpoke1024,134:poke55296,7:goto1270
210 ifjd=8thenifp<>189thenp=p+1:ifp=195thenp=187
220 ifjd=4thenifp<>193thenp=p-1:ifp=186thenp=194
225 ifam=.then240
226 iffe<20thenpt=.:goto60
227 gosub1950
240 iffe<4then270
250 iffr<>16orpeek(653)thenpokew7,31:q=8:fe=fe-4:goto280
270 q=.:m2=m2+gv:pokew7,29:pokesf,128:goto330
280 pokes+24,15:pokes+5,128:pokes+6,128:pokes+1,4:pokes,100:pokes+4,129
290 onp-186goto300,305,315,330,330,330,320,310
300 m2=m2-th:goto330
305 m2=m2-th+1:hm=hm+1:goto330
310 m2=m2-th+1:hm=hm-1:goto330
315 m2=m2-t6:hm=hm+1:goto330
320 m2=m2-t6:hm=hm-1
330 pz=pz+m2*ka:ifpz<25thenpz=25
340 po=int(pz):pp=pp+hm
360 ife2=.thenifpp<1thene2=1:pp=87+pp:pokew8,fh:goto430
370 ife2=1thenifpp<1thene2=.:pp=255+pp:pokew8,fm:goto430
380 ife2=.thenifpp>255thene2=1:pp=pp-255:pokew8,fh:goto430
390 ife2thenifpp>86thene2=.:pp=pp-87:pokew8,fm
430 pokew0,pp:pokew1,po:pokew2,pp:pokew3,po
440 pokepn,p:pokenq,p+q
470 ifpeek(w9)and1thenifpo>120thenhz=1:rem read every step; the latch must not go stale
480 ifpo>190thenife2=.thenifpp<5thenhz=1
490 ifpo>195thenife2thenifpp>84thenhz=1
495 return
500 vm=int(m2/10):ifhm>20thenhm=20
510 ifhm<-20thenhm=-20
520 c1=5:ifvm>=3thenc1=7
525 ifvm>slthenc1=2
530 ifvm<>om2thenom2=vm:gosub1620
532 ifc1<>o1theno1=c1:cd=55371:cc=c1:gosub1680
540 c2=5:iffe<400thenc2=7
545 iffe<100thenc2=2
550 iffe<>ofethenofe=fe:gosub1640
552 ifc2<>o2theno2=c2:cd=55451:cc=c2:gosub1680
560 c3=5:ifhm<>.thenc3=7
562 ifhm>2orhm<-2thenc3=2
570 ifhm<>ohmthenohm=hm:gosub1660
572 ifc3<>o3theno3=c3:cd=55531:cc=c3:gosub1680
630 goto160
639 vm=int(m2/10):xz=.:rem verdict must use current velocity, not the hud copy
640 ifhm>2goto1320
641 ifhm<-2goto1320
642 ifp<>187goto1320
644 ifvm>slgoto1320
649 pf=pp:ife2thenpf=pf+256
650 lz=.:fori=1to5
660 ifpf<px(i)orpf>=px(i)+pw(i)*8then690
670 ifabs(po-py(i))>4then690
680 lz=i:tp=tp+pb(i):i=5
690 next
700 iflz=.thenxz=1:goto1320
705 ifrf(lz)<>.andfe<=399thenfe=1000:e7=1
720 pokev+21,29:pokew8,fm:hz=.:gosub1210
730 pokes+4,128:forx=1to200:next
740 cx=px(lz)+pw(lz)*4:ifabs(pf-cx)<3thenbs=int(pb(lz)*2/3)
752 tp=tp-abs(vm)*30
753 tp=tp-abs(hm)*30
754 tp=tp-(fu-fe)
755 tp=tp+bs
760 pt=pt+tp:ifpt<1thenpt=.
770 ifcrthengosub1700
775 bs=bs-(fu-fe):ifbs>.thena$="{cyn} "+str$(bs)+" bonus":gosub982
778 a$="{cyn}"+str$(int(tp))+" points":gosub982
780 ife7thene7=.:a$="{lgrn}fuel tanks full":gosub982
785 ifnm<.orfe<4thennf=1:nm=.
790 ifnf=1thena$="{rvof}{orng}game over":ep=250:hp=-20:ifpt>hsthenifam=.thenhs=pt:gosub1500
795 ifnfthenifamthenpt=.:goto60
797 ifnfgoto982
840 tp=.:fu=fe:bs=.:forx=1to100:next:goto90
960 getz$:jv=peek(js):fr=jvand16
965 iffr<>16thenz$="{f7}"
970 ifz$="{f7}"thenpt=.:tp=.:nm=4:nf=.:fe=1000:n2=ni:gosub986:gosub1100:goto840
980 goto960
982 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}"bl$;
983 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}";spc((42-len(a$))/2);:forx=1tolen(a$):printmid$(a$,x,1);
984 gosub990:next
985 forx=1to1500:next:ifnfgoto960
986 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}"bl$;
987 return
988 rem skip voice 3: zero freq freezes its noise register
989 rem
990 forl=54272to54285:pokel,0:next:forl=54293to54296:pokel,0:next
1000 poke54296,10:poke54277,64:poke54273,17:poke54272,37:poke54276,17
1010 fort=1to20:next:poke54276,16:return
1020 print"{clr}":poke53280,11:poke53281,0:pokew7,.
1030 poke214,5:print:printtab(11)"{lblu}l u n a l i g h t";
1040 poke214,12:print:print"{lblu}   public domain 2024 steven hardison"
1045 poke214,14:print:printtab(10)"{cyn}f5 moon   f3 mars"
1060 printtab(11);
1070 print"press {rvon}f7{rvof} to start"
1072 sys17408:rem tod entropy, ~3s; f5/f3 rejoin at 1075 to skip it
1075 printtab(11);:ifbp=.thenprint"{yel}planet: moon {left}"
1076 ifbpthenprint"{orng}planet: mars {left}"
1077 printtab(7)"{lblu}attract mode in 20 seconds"
1078 t0=ti
1080 getf$:iff$="{f5}"thenbp=.:gosub1800:goto1075
1085 iff$="{f3}"thenbp=1:gosub1800:goto1075
1090 iff$="{f7}"thensys17414:return
1091 iff$<>""thent0=ti
1092 if(peek(56320)and31)<>31thent0=ti
1093 tt=ti-t0:iftt<.thentt=tt+5184000
1094 iftt>=1200thenam=1:return
1095 goto1080
1100 rem sid-random mountain terrain: high, low and middle pads
1105 print"{clr}":pokew7,.:gosub1850:sys17411:ri=.:tc=12:td=11:ifbp thentc=2:td=9
1107 hh=3:sg=.
1110 forc=0to39:ifsg>0then1122
1115 gosub1900:tg=1+int(rv*12/256):gosub1900:sg=3+int(rv*5/256)
1120 iftg=hhthentg=13-hh
1122 ds=sgn(tg-hh):gosub1900:ifrv<64thends=ds*2
1125 hh=hh+ds:ifhh<1thenhh=1
1130 ifhh>12thenhh=12
1132 h(c)=hh:sg=sg-1:next
1133 forc=1to38:gosub1900:ifrv<52thenh(c)=h(c)+(rvand2)-1
1134 ifh(c)<1thenh(c)=1
1135 ifh(c)>12thenh(c)=12
1136 next:px(1)=1:px(2)=9:px(3)=17:px(4)=25:px(5)=33
1137 gosub1900:ro=int(rv*5/256):fz=.
1140 fori=1to5:gosub1900:cs=px(i)+int(rv*3/256)
1142 gosub1900:pw(i)=3+(rvand1):ce=cs+pw(i)-1:rf(i)=.
1143 zz=i+ro:ifzz>5thenzz=zz-5
1145 ifzz=1orzz=3thengosub1900:hh=9+int(rv*4/256):goto1151
1147 ifzz=2orzz=5thengosub1900:hh=3+(rvand1):goto1151
1150 gosub1900:hh=5+int(rv*4/256)
1151 pb(i)=600:ifhh>8thenpb(i)=800
1152 ifhh<5thenpb(i)=500:iffz=.thenrf(i)=1:fz=1:rz=i
1153 ph(i)=hh:forc=cstoce:h(c)=hh:next
1155 ford=1to2:ifcs-d>=.thenifhh>8thenh(cs-d)=hh-d
1157 ifce+d<40thenifhh>8thenh(ce+d)=hh-d
1160 ifcs-d>=.thenifhh<4thenh(cs-d)=hh+d*2
1162 ifce+d<40thenifhh<4thenh(ce+d)=hh+d*2
1163 ifcs-d>=.thenifhh>=4andhh<=8thenh(cs-d)=hh+int(d/2)
1164 ifce+d<40thenifhh>=4andhh<=8thenh(ce+d)=hh+int(d/2)
1165 nextd:py(i)=242-hh*8:px(i)=24+cs*8:nexti
1170 rem pad bonuses follow elevation; first low pad refuels
1175 forc=0to39:ht=h(c):forln=0to12
1180 pk=sn+ln*40+c:ifln<13-htthen1190
1182 pokepk,160:gosub1900:pokepk+bc,tc:if(rvand3)=((c*17+ln*31)and3)thenpokepk+bc,td
1190 nextln:nextc
1192 fori=1to5:cs=int((px(i)-24)/8):ce=cs+pw(i)-1:ln=13-ph(i):pk=sn+ln*40
1195 forc=cstoce:pokepk+c,100:pokepk+c+bc,5:nextc
1196 pokepk+cs+bc,7:pokepk+ce+bc,7:nexti
1197 fx=px(rz)-3:fm=.:iffx>255thenfm=16:fx=fx-256
1198 fh=227+fm:fy=py(rz)-27:gosub1210
1200 poke56295,14:poke2023,160:print"{home}":om2=-999:ofe=-999:ohm=-999
1205 o1=-1:o2=-1:o3=-1:return
1210 rem refuel flag on sprite 4; the explosion borrows it, so re-establish all of it
1212 poke2044,243:pokev+8,fx:pokev+9,fy:pokev+43,3:pokev+23,16:pokev+28,.:return
1270 getz$:jv=peek(js):fr=jvand16
1275 iffr<>16thenz$="{f1}"
1280 ifz$="{f1}"thenpoke1024,160:poke55296,0:lt=ti:return
1290 ifz$="{f7}"then20
1300 ifz$="{home}"thenprintrv$;:stop
1310 goto1270
1320 pokes+4,128:pr=pp:lp=pp:cr=1
1325 pokepn+4,203:pokepn+5,213:pokepn+6,223:pokepn+7,233
1330 ifpp+12>255thenpokev+16,96:pr=pp-256
1340 pokev+10,pr+12:pokev+9,po-10:pokev+12,pr+12:pokev+15,po+10
1350 ifpeek(v+16)<>.thenifpp-12<.thenpokev+16,96:lp=256+pp:goto1370
1360 ifpp-12<.thenlp=15
1370 pokev+14,lp-12:pokev+13,po+10:pokev+8,lp-12:pokev+11,po-10
1375 forss=1to4:pokev+42+ss,7:next
1380 pokev+28,240:pokev+37,11:pokev+38,2:pokev+39,0:pokev+40,0:pokev+21,252
1390 forex=203to212:pokepn+4,ex:pokepn+5,ex+10:pokepn+6,ex+20:pokepn+7,ex+30
1395 pokes+24,212-ex:pokes+4,129:pokes+5,15:pokes+1,5:pokes,20:ford=1to60:next:nextex
1410 pokes+4,0:pokes+5,0:pokev+1,12:pokev+21,12
1415 nm=nm-1:n2=n2-ns:lz=.:bs=.:hz=.:tp=.
1420 goto720
1500 poke214,23:print:print"{rvon}{lblu}                                       ";
1510 poke214,23:print:print"{rvon}{lblu} hi";hs;tab(17);"score";pt;:printtab(32);nm;"lems";
1515 ifamthenprint"{home}{rvon}{lblu} attract "
1520 return
1600 print"{home}{down}"spc(35)t1$
1612 print"{home}{down}{down}{down}"spc(35)t2$
1614 print"{home}{down}{down}{down}{down}{down}"spc(35)t3$
1616 return
1620 a$=right$("   "+str$(vm),3):ad=1024+80+36
1624 fori=0to2:pokead+i,asc(mid$(a$,i+1,1)):next:return
1640 a$=right$("    "+str$(fe),4):ad=1024+160+35
1642 fori=0to3:pokead+i,asc(mid$(a$,i+1,1)):next:return
1660 a$=right$("   "+str$(hm),3):ad=1024+240+36
1662 fori=0to2:pokead+i,asc(mid$(a$,i+1,1)):next:return
1680 rem colour the 4-cell label row and the value row beneath it
1682 fori=.to3:pokecd+i,cc:pokecd+40+i,cc:next:return
1700 rem crash post-mortem: cause line, then a rotating consequence
1702 cr=.:cv=abs(vm):ch=abs(hm)
1704 a$="{red}you rearranged the landscape"
1706 ifxzthena$="{red}boulders are not landing pads"
1708 ifch>2thena$="{red}you cartwheeled"+str$(ch*7)+" feet"
1710 ifp<>187thena$="{red}lems do not land sideways"
1712 ifcv>slthena$="{red}new crater"+str$(cv*3)+" feet deep"
1714 gosub982:cn=(cn+1+peek(162))and15:ifcn>12thencn=cn-13:rem jiffy, not osc3; 13 items
1716 restore:forx=.tocn:readq$:next
1718 a$="{yel}"+q$:gosub982:return
1800 rem moon bp=0 / mars bp=1; gv/th tenths of velocity per physics step
1810 ifbp=.thengv=20:th=20:ni=18:nb=28:nc=35:ns=3:sl=5:t6=3:return
1820 gv=46:th=34:ni=24:nb=33:nc=41:ns=4:sl=8:t6=5:return
1850 rem sid voice 3 noise oscillator random source
1860 poke54286,255:poke54287,255:poke54290,128:return
1899 rem table is refilled per terrain; worst case is 654 draws of 1024
1900 rv=peek(rb+ri):ri=ri+1:return
1920 rem next demo pad; aim where the lander rests wholly on pad cells
1922 ak=ak+1:ifak>5thenak=1
1924 al=ak:tx=px(al)+(pw(al)-3)*4:ap=.:return
1950 rem autopilot: cruise clear of terrain, then drop straight in
1952 ae=tx-pp:ife2thenae=ae-256
1954 ifapthen1980
1956 av=.:ifpo>112thenav=-4
1958 ifpo<96thenav=4
1960 aa=abs(ae):ah=.:ifaa>.thenah=1
1961 ifaa>4thenah=2
1962 ifaa>12thenah=3
1963 ifaa>25thenah=4
1964 ifaa>40thenah=6
1966 ifae<.thenah=-ah
1968 ifae=.thenifhm=.thenifpo>96thenap=1
1970 goto2000
1980 ag=py(al)-po:av=3
1982 ifag>8thenav=6
1984 ifag>25thenav=12
1986 ifag>60thenav=25
1988 ah=.:ifae<>.thenap=.
2000 af=.:ifint(m2/10)>avthenaf=1
2005 ifhm<ahthenp=188:fr=.:return
2010 ifhm>ahthenp=194:fr=.:return
2015 p=187:fr=16:ifafthenfr=.
2020 return
2100 rem crash consequences; restore indexes these by jiffy
2102 data"salvage crews found one boot"
2104 data"houston is billing your estate"
2106 data"taxpayers demand an inquiry"
2108 data"your damage deposit is forfeit"
2110 data"next of kin have been notified"
2112 data"underwriters call it pilot error"
2114 data"you also flattened the flag"
2116 data"the parked rover is now scrap"
2118 data"another 100 megabucks well spent"
2122 data"aux tanks are now lunar confetti"
2124 data"your crater needs its own postcode"
2126 data"mission control muted your channel"
2130 data"your flight recorder just resigned"
