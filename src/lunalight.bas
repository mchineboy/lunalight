  10 rem save"luna081426",8,1
  20 clr:printchr$(8):poke56576,(peek(56576)and252)or1:poke648,132:poke53272,20:rv$="luna2":bl$="                                        "
  25 dimpx(5),pw(5),py(5),pb(5),rf(5),ph(5),h(39)
  30 sys16896:sys17408:gosub1020:sys16899:gosub990
  40 print"{clr}":v=53248:s=54272:c$="{left} ":poke53280,11:poke53281,0:sn=34272:bc=21504:rb=18432:rz=1
  50 t1$="{rvon}vel {rvof} ":t2$="{rvon}fuel{rvof} ":t3$="{rvon}horz{rvof} ":ep=250:hp=-20:lc=55296
  60 pn=34808:fe=1000:fu=fe:nm=4:nf=.:n2=25:gosub1100:ifamthengosub1920
  70 pokev+41,1:pokev+42,6:poke34810,253:poke34811,254
  80 pokev+4,60:pokev+5,60:pokev+6,60:pokev+7,60
  90 po=28:pp=ep:hm=hp:ifamthenpp=tx:hm=.
  95 ep=ep-23:ifep=20thenep=250
  100 hp=hp+4:ifhp>25thenhp=-25
  110 e2=.:pokev+39,0:pokev+40,0:pokev+16,fm
  112 ifamthenifpp>255thene2=1:pp=pp-256:pokev+16,fh
  120 ifn2>47thenn2=37
  130 p=187:q=8:m2=n2:n2=n2+4:pokev+17,peek(v+17)or16
  135 pokev+39,12:pokev+40,8:gosub1500
  160 getz$:jv=peek(56320):ifamthen1950
  165 ifz$<>""thengosub1980
  168 if(jvand15)=15then190
  170 if(jvand15)=7thenp=p+1:ifp=190thenp=189:goto200
  172 ifp=195thenp=187:goto200
  180 if(jvand15)=11thenp=p-1:ifp=186thenp=194:goto200
  182 ifp=192thenp=193:goto200
  190 ifz$="{f1}"thenpoke33792,134:poke55296,7:goto1270
  200 iffe=.goto230
  220 if(jvand16)=.orpeek(653)thenpokev+21,31:q=8:goto240
  230 ifq=.thenm2=m2+.6:pokes+4,128:goto330
  235 q=.:m2=m2+.6:pokev+21,29:pokes+4,128:goto330
  240 pokes+24,15:pokes+5,128:pokes+6,128:pokes+1,8:pokes,200:pokes+4,129
  245 onp-186goto250,260,280,330,330,330,290,270
  250 m2=m2-.6:fe=fe-1:goto330
  260 m2=m2-.6:hm=hm+1:fe=fe-2:goto330
  270 m2=m2-.6:hm=hm-1:fe=fe-2:goto330
  280 m2=m2-.2:hm=hm+2:fe=fe-3:goto330
  290 m2=m2-.2:hm=hm-2:fe=fe-3:goto330
  330 onsgn(m2)+2goto332,350,340
  332 po=po-(.1+(-m2/20)):goto350
  340 po=po+(.1+(m2/20))
  350 onsgn(hm)+2goto360,430,400
  360 pp=pp-(-hm/4)
  370 ife2=.thenifpp<.thene2=1:pp=87+pp:pokev+16,fh:goto430
  380 ife2thenifpp<.thene2=.:pp=255+pp:pokev+16,fm
  390 goto430
  400 pp=pp+(hm/4)
  410 ife2=.thenifpp>255thene2=1:pp=pp-255:pokev+16,fh:goto430
  420 ife2thenifpp>87thene2=.:pp=pp-87:pokev+16,fm
  430 pokev,pp:pokev+1,po:pokev+2,pp:pokev+3,po
  440 pokepn,p:pokepn+1,p+q
  460 ifpo<25thenpo=25
  480 ifpo>230thenhm=10:goto1320
  500 ifm2<3thenprint"{grn}";:goto530
  510 print"{yel}";
  515 ifm2>5thenprint"{red}";
  530 print"{home}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t1$
  531 print"{home}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"int(m2);c$
  535 iffe<1thenfe=.
  540 iffe>399thenprint"{grn}";:goto570
  550 iffe<100thenprint"{red}";:goto570
  560 print"{yel}";
  570 print"{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t2$;
  571 print"{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"fe;c$
  580 ifhm>99thenhm=98:goto610
  590 ifhm<-99thenhm=-98:goto610
  600 ifhm=.thenprint"{grn}";:goto620
  605 ifhm>-3thenifhm<3thenprint"{yel}";:goto620
  610 print"{red}";
  620 print"{home}{down}{down}{down}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t3$;
  621 print"{home}{down}{down}{down}{down}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"hm;c$
  630 ifpeek(v+31)and1thenifpo>120goto640
  635 goto160
  640 ifhm>2goto1320
  641 ifhm<-2goto1320
  642 ifp<>187goto1320
  644 ifint(m2)>5goto1320
  649 pf=int(pp)+12:ife2thenpf=pf+256
  650 lz=.:fori=1to5
  660 ifpf<px(i)orpf>=px(i)+pw(i)*8then690
  670 ifabs(po-py(i))>4then690
  680 lz=i:tp=tp+pb(i):i=5
  690 next
  700 iflz=.thenxz=1:goto1320
  705 ifrf(lz)<>.andfe<=399thenfe=1000:e7=1
  706 goto720
  710 nm=nm-1:n2=n2-7:lz=.
  720 pokev+21,29:pokev+16,fm:gosub1210
  730 pokes+4,128:forx=1to500:next
  740 iflz>0thencx=px(lz)+pw(lz)*4:ifabs(pf-cx)<3thenbs=int(pb(lz)*2/3)
  752 tp=tp-abs(int(m2))*30
  753 tp=tp-abs(hm)*30
  754 tp=tp-(fu-fe)
  755 tp=tp+bs
  760 pt=pt+tp:ifpt<1thenpt=.
  770 ifcrthengosub1900
  775 bs=bs-(fu-fe):ifbs>.thena$="{cyn} "+str$(bs)+" bonus":gosub982
  778 a$="{cyn}"+str$(int(tp))+" points":gosub982
  780 ife7thene7=.:a$="{lgrn}fuel tanks full":gosub982
  785 ifnm<.orfe<1thennf=1:nm=.
  790 ifnf=1thena$="{rvof}{orng}game over":ep=250:hp=-20:ifpt>hsthenifam=.thenhs=pt:gosub1500
  792 ifnfthenifamthenpt=.:nm=4:nf=.:fe=1000:goto835
  795 ifnfgoto982
  835 ifamthengosub1920
  840 tp=.:fu=fe:bs=.:forx=1to200:next:goto90
  900 rv=peek(rb+ri):ri=ri+1:return
  960 getz$
  970 ifz$="{f7}"thenpt=.:tp=.:nm=4:nf=.:fe=1000:n2=25:gosub986:gosub1100:goto840
  980 goto960
  982 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}";spc((42-len(a$))/2);:forx=1tolen(a$):printmid$(a$,x,1);
  983 gosub990:next
  984 forx=1to3000:next:ifnfgoto960
  986 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}"bl$;:return
  990 forl=54272to54296:pokel,0:next
  1000 poke54296,10:poke54277,64:poke54273,17:poke54272,37:poke54276,17
  1010 fort=1to20:next:poke54276,16:return
  1020 am=.:print"{clr}":poke53280,11:poke53281,0
  1030 poke214,5:print:printtab(11)"{lblu}l u n a l i g h t";
  1040 poke214,16:print:print"{lblu}   public domain 2024 steven hardison"
  1050 print"{down}";
  1060 printtab(11);
  1070 print"press {rvon}f7{rvof} to start"
  1072 printtab(7)"{lblu}attract mode in 20 seconds"
  1074 t0=ti
  1080 getf$:iff$="{f7}"thenreturn
  1082 iff$<>""thent0=ti
  1084 if(peek(56320)and31)<>31thent0=ti
  1086 tt=ti-t0:iftt<.thentt=tt+5184000
  1088 iftt>=1200thenam=1:return
  1090 goto1080
  1100 print"{clr}":pokev+21,0:sys17411:ri=.:tc=12:td=11
  1102 hh=3:sg=.
  1110 forc=0to39:ifsg>0then1122
  1115 gosub900:tg=1+int(rv*12/256):gosub900:sg=3+int(rv*5/256)
  1120 iftg=hhthentg=13-hh
  1122 ds=sgn(tg-hh):gosub900:ifrv<64thends=ds*2
  1125 hh=hh+ds:ifhh<1thenhh=1
  1130 ifhh>12thenhh=12
  1132 h(c)=hh:sg=sg-1:next
  1133 forc=1to38:gosub900:ifrv<52thenh(c)=h(c)+(rvand2)-1
  1134 ifh(c)<1thenh(c)=1
  1135 ifh(c)>12thenh(c)=12
  1136 next:px(1)=1:px(2)=9:px(3)=17:px(4)=25:px(5)=33
  1137 gosub900:ro=int(rv*5/256):fz=.
  1140 fori=1to5:gosub900:cs=px(i)+int(rv*3/256)
  1142 gosub900:pw(i)=3+(rvand1):ce=cs+pw(i)-1:rf(i)=.
  1143 zz=i+ro:ifzz>5thenzz=zz-5
  1145 ifzz=1orzz=3thengosub900:hh=9+int(rv*4/256):goto1151
  1147 ifzz=2orzz=5thengosub900:hh=3+(rvand1):goto1151
  1150 gosub900:hh=5+int(rv*4/256)
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
  1175 forc=0to39:ht=h(c):forln=13-htto12
  1180 pk=sn+ln*40+c:pokepk,160:pokepk+bc,tc:if((c*17+ln*31)and3)=1thenpokepk+bc,td
  1190 nextln:nextc
  1192 fori=1to5:cs=int((px(i)-24)/8):ce=cs+pw(i)-1:ln=13-ph(i):pk=sn+ln*40
  1195 forc=cstoce:pokepk+c,100:pokepk+c+bc,5:nextc
  1196 pokepk+cs+bc,7:pokepk+ce+bc,7:nexti
  1197 fx=px(rz)-3:fm=.:iffx>255thenfm=16:fx=fx-256
  1198 fh=227+fm:fy=py(rz)-7:gosub1210
  1200 poke56295,14:poke34791,160:print"{home}":return
  1210 poke34812,243:pokev+8,fx:pokev+9,fy:pokev+43,14:pokev+23,.:pokev+28,.:return
  1270 getz$
  1280 ifz$="{f1}"thenpoke33792,160:poke55296,0:goto200
  1290 ifz$="{f7}"then20
  1300 ifz$="{home}"thenprintrv$;:stop
  1310 goto1270
  1320 pokes+4,128:forss=1to4:pokev+42+ss,7:next:pp=int(pp):pr=pp:pl=pp:cr=1
  1325 pokepn+4,203:pokepn+5,213:pokepn+6,223:pokepn+7,233
  1330 ifpp+12>255thenpokev+16,96:pr=pp-256
  1340 pokev+10,pr+12:pokev+9,po-10:pokev+12,pr+12:pokev+15,po+10
  1350 ifpeek(v+16)<>.thenifpp-12<.thenpokev+16,96:pl=256+pp:goto1370
  1360 ifpp-12<.thenpl=15
  1370 pokev+14,pl-12:pokev+13,po+10:pokev+8,pl-12:pokev+11,po-10:pokev+21,252
  1380 pokev+28,240:pokev+37,11:pokev+38,2:pokev+39,0:pokev+40,0
  1390 forex=203to212:pokepn+4,ex:pokepn+5,ex+10:pokepn+6,ex+20:pokepn+7,ex+30
  1400 pokes+24,212-ex:pokes+4,129:pokes+5,15:pokes+1,5:pokes,20:ford=1to100:next:nextex
  1410 pokes+4,0:pokes+5,0:pokev+1,12:pokev+21,12
  1420 goto710
  1500 poke214,23:print:print"{rvon}{lblu}                                       ";
  1510 poke214,23:print:print"{rvon}{lblu} hi";hs;tab(17);"score";pt;:printtab(32);nm;"lems";
  1515 ifamthenprint"{home}{rvon}{lblu} attract "
  1520 return
  1900 rem crash post-mortem: exactly one line, cause or consequence, by rng
  1902 cr=.:gosub900:ifrv<128goto1914
  1903 cv=abs(int(m2)):ch=abs(hm)
  1904 a$="{red}you rearranged the landscape"
  1906 ifxzthena$="{red}boulders are not landing pads"
  1908 ifch>2thena$="{red}you cartwheeled"+str$(ch*7)+" feet"
  1910 ifp<>187thena$="{red}lems do not land sideways"
  1912 ifcv>5thena$="{red}new crater"+str$(cv*3)+" feet deep"
  1913 xz=.:gosub982:return
  1914 cn=(cn+1+peek(162))and15:ifcn>12thencn=cn-13
  1916 restore:forx=.tocn:readq$:next
  1918 xz=.:a$="{yel}"+q$:gosub982:return
  1920 rem cycle demo pads and spawn nearby; normal terrain metadata is authoritative
  1922 ak=ak+1:ifak>5thenak=1
  1923 al=ak:iffe<400thenifrf(rz)thenal=rz
 1924 tx=px(al)+(pw(al)-3)*4:return
  1950 rem float autopilot: target m2 and hm, then feed normal controls
  1951 ifz$<>""or(jvand31)<>31orpeek(653)then20
  1952 ag=py(al)-po:av=12:ifag<60thenav=8
 1954 ifag<25thenav=4
 1956 ifag<12thenav=1
  1960 ae=tx-pp:ife2thenae=ae-256
  1962 aa=abs(ae):ah=.:ifaa>2thenah=1
  1964 ifaa>12thenah=2
  1966 ifaa>24thenah=3
  1968 ifae<.thenah=-ah
 1970 jt=16:ifm2>avthenjt=.
 1971 jv=15+jt
 1972 ifhm<ahthenifp<>188thenjv=7+jt:goto170
 1973 ifhm<ahthenjv=15:goto170
 1974 ifhm>ahthenifp<>194thenjv=11+jt:goto170
 1975 ifhm>ahthenjv=15:goto170
 1976 ifp=188orp=189thenjv=11+jt:goto170
 1977 ifp<>187thenjv=7+jt
  1978 goto170
  1980 ifz$="{rght}"thenjv=(jvand16)+7
  1982 ifz$="{down}"thenjv=(jvand16)+11
  1984 return
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
