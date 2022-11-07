import streamlit as st
import plotly.express as px
import requests
import parsel
import pandas as pd
import io

SOURCE_URL = 'https://www.hakubavalley.com/en/ski_resort_info_en/'


def _parse_ski_resort_info(html, debug_log=False):
    """Parses the HTML on SOURCE_URL"""
    resort_dicts = []
    document = parsel.Selector(html)
    resorts = document.css('.spec-item')
    if debug_log:
        print(f'Found {len(resorts)}')
    for resort in resorts:
        name = resort.css('.gelande_name::text').get()
        specs = resort.css('.spec-info dl dd::text').getall()[0:6]
        elevation = resort.css('.altitude p::text').getall()
        levels = resort.css('.course-level p::text').getall()
        website = resort.css('.site_url a::attr(href)').get()
        trail_map = resort.css('.btn-wht-blk a::attr(href)').get()
        resort_dicts.append(dict(
            name=name,
            length=int(specs[0].replace(',', '')),
            total_trails_length=int(specs[1].replace(',', '')),
            area=int(specs[2].replace(',', '')),
            gondolas=int(specs[3].replace(',', '')),
            chairs=int(specs[4].replace(',', '')),
            trails=int(specs[5].replace(',', '')),
            max_elevation=int(elevation[0].replace(',', '')),
            base_elevation=int(elevation[2].replace(',', '')),
            vertical=int(elevation[1].replace(',', '')),
            beginner_pct=int(levels[0]) / 100.0,
            intermediate_pct=int(levels[1]) / 100.0,
            advanced_pct=int(levels[2]) / 100.0,
            website=website,
            trail_map=trail_map,
        ))
    return pd.DataFrame(resort_dicts)


@st.experimental_memo
def get_resort_info(debug_log=True):
    """Gets info from SOURCE_URL"""
    # Pull down page
    response = requests.get(SOURCE_URL)
    df = _parse_ski_resort_info(response.text, debug_log)

    # Cleanup resort names
    df = df.assign(name=lambda df: (
        df['name']
        .str.replace(' Snow Resort', '')
        .str.replace(' Snow Field', '')
        .str.replace(" Park", '')
        .str.replace(" Resort", '')
        .str.replace(" Mountain", '')
        .str.replace(' Winter Sports', '')
        .str.replace('ABLE ', '')
        .str.replace('Hakuba ', ''))
                   .str.replace('47', 'Hakuba 47'))

    # Get trails by type
    df = (df
          .assign(beginner_trails=lambda df: df['beginner_pct'] * df['trails'])
          .assign(intermediate_trails=lambda df: df['intermediate_pct'] * df['trails'])
          .assign(advanced_trails=lambda df: df['advanced_pct'] * df['trails'])
          .set_index('name')
          )

    return df.sort_values('area', ascending=False)


def _combine_resorts(df, remove_parts_of_group=True):
    """Combine Goryu and Hakuba 47"""
    combined = (df
                .loc[['Goryu', 'Hakuba 47']]
                .agg({'length': 'max',
                      'total_trails_length': 'sum',
                      'area': 'sum',
                      'gondolas': 'sum',
                      'chairs': 'sum',
                      'trails': 'sum',
                      'max_elevation': 'max',
                      'base_elevation': 'min',
                      'beginner_trails': 'sum',
                      'intermediate_trails': 'sum',
                      'advanced_trails': 'sum'})
                )
    combined['vertical'] = combined['max_elevation'] - combined['base_elevation']
    combined['beginner_pct'] = combined['beginner_trails'] / combined['trails']
    combined['intermediate_pct'] = combined['intermediate_trails'] / combined['trails']
    combined['advanced_pct'] = combined['advanced_trails'] / combined['trails']

    df.loc['Hakuba 47 + Goryu'] = combined
    df = df.astype({'gondolas': 'int', 'chairs': 'int'})

    if remove_parts_of_group:
        df = df.drop(index=['Hakuba 47', 'Goryu'])

    return df.sort_values('area', ascending=False)


@st.experimental_memo
def convert_to_excel(df: pd.DataFrame):
    file = io.BytesIO()
    df.to_excel(file)
    file.seek(0)
    return file


@st.experimental_memo
def convert_to_csv(df: pd.DataFrame):
    file = io.BytesIO()
    df.to_csv(file, encoding='utf-8')
    file.seek(0)
    return file


def run():
    st.set_page_config(layout='wide', page_title='Hakuba Valley Resorts')

    st.title('Hakuba Valley Ski Resort Comparison!!!')
    st.markdown(f'''
    Taking the data from {SOURCE_URL} and presenting them into generic charts to make it easier to compare.
    
    Hakuba 47 and Goryu Ski Resorts are connected so by default they're shown together.
    
    Hello World
    
    ''')

    tab_chart, tab_maps = st.tabs(['Charts', 'Maps'])
    with tab_chart:
        resorts_df = get_resort_info(True)

        with st.expander("Source Data", expanded=False):
            st.write(resorts_df)
            st.download_button(
                'Download as Excel', convert_to_excel(resorts_df), 'hakuba_data.xlsx', mime='application/vnd.ms-excel')
            st.download_button(
                'Download as CSV', convert_to_csv(resorts_df), 'hakuba_data.csv', mime='text/csv')

        combine_resorts = st.checkbox('Combine Hakuba 47 and Goryu?', value=True)
        if combine_resorts:
            resorts_df = _combine_resorts(resorts_df)

        st.plotly_chart(px.bar(resorts_df.assign(
            label=lambda df: df['gondolas'].apply(lambda f: f'{f} gondolas, ') + df['chairs'].apply(
                lambda f: f'{f} chairs')),
            y='area',
            title='Skiable Area by Resort',
            text='label',
        ).update_layout(xaxis_title='', yaxis_title='ha'), use_container_width=True)

        st.plotly_chart(
            px.bar(resorts_df,
                   y='total_trails_length',
                   title='Total Trail Length by Resort'
                   ).update_layout(xaxis_title='', yaxis_title='m')
            , use_container_width=True)

        st.plotly_chart(
            px.bar(resorts_df,
                   y=['beginner_trails', 'intermediate_trails', 'advanced_trails'],
                   title='Trail Type by Resort',
                   color_discrete_map={'beginner_trails': '#86c96b', 'intermediate_trails': '#db3a2e',
                                           'advanced_trails': '#555'},
                   ).update_layout(showlegend=False, yaxis_title='trails', xaxis_title='')

            , use_container_width=True)

        st.plotly_chart(
            px.bar(resorts_df,
                   y=['beginner_pct', 'intermediate_pct', 'advanced_pct'],
                   title='Trail Type by Resort',
                   color_discrete_map={'beginner_pct': '#86c96b', 'intermediate_pct': '#db3a2e', 'advanced_pct': '#555'},
                   ).update_layout(showlegend=False, yaxis_title='%', yaxis_tickformat='0.0%', xaxis_title='')

            , use_container_width=True)

        st.plotly_chart(
            px.bar(resorts_df.assign(label=lambda df: df['max_elevation'].apply(lambda x: f'max elev={x:.0f}m')),
                   y='vertical',
                   text='label',
                   title='Vertical and Max Elevation by Resort',
                   barmode='group'
                   ).update_layout(showlegend=False, yaxis_title='vertical (m)', xaxis_title='')
            , use_container_width=True)

    with tab_maps:
        st.markdown('''
    Old, from Google Image Search
    
    ![Geographic Layout](https://skimap.org/data/5891/1/1477283996.jpg)
   
    From a handy site with village maps, trail maps, etc: https://www.samuraisnow.com/hakuba-maps
    
    ![Geographic Layout](https://www.samuraisnow.com/sites/default/files/_hakuba/Hakuba-Ski-Map.jpg)
    
    ![Simplified Layout](https://www.samuraisnow.com/sites/default/files/_hakuba/Hakuba-Valley-Map-Thumb-1.jpeg)
        ''')
if __name__ == '__main__':
    run()
